# -*- coding: utf-8 -*-
"""
Sinh bộ dữ liệu mẫu cho ứng dụng quản lý nhu yếu phẩm.

Mô phỏng một cửa hàng / kho nhỏ từ 01/01/2026 đến 12/11/2026 (4 quý):
  - mỗi ngày xuất bán một lượng hàng dao động quanh mức tiêu thụ bình quân,
    có mùa vụ (Tết tháng 1–2 bán chạy hơn)
  - hàng nhập theo lô; xuất theo nguyên tắc nhập trước – xuất trước (FIFO)
  - lô hàng quá hạn sử dụng thì bị HỦY (phiếu "dispose")
  - khi tồn kho xuống dưới mức tối thiểu thì (thường) nhập thêm một lô
  - quy trình được CẢI TIẾN dần qua từng quý: nhập kịp thời hơn, lô hàng mau
    hỏng nhỏ lại cho vừa sức bán → ít hết hàng, ít hủy hàng (để thấy KPI cải thiện)
  - một vài mặt hàng ngừng nhập ở cuối kỳ → có ví dụ "Sắp hết" / "Hết hàng"

Chạy:  python data/generate_sample_data.py
Kết quả: data/raw/products.csv và data/raw/transactions.csv
(Sau khi sinh lại, xóa file data/hanghoa.db để app nạp dữ liệu mới.)
"""

from __future__ import annotations

import datetime as dt
import os
from collections import deque

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)  # cố định seed để tái lập được

START = dt.date(2026, 1, 1)
END = dt.date(2026, 11, 12)

# Đơn vị đếm theo cái/chai/gói... thì số lượng là số nguyên
COUNT_UNITS = {"gói", "chai", "hộp", "lon", "túi", "quả", "cái"}
LONG_LIFE_DAYS = 90

# ---------------------------------------------------------------------------
# Danh sách sản phẩm
#   price     : đơn giá tham khảo (đ / đơn vị)
#   min_stock : mức tồn tối thiểu (lượng dự trữ phải giữ)
#   daily     : tiêu thụ bình quân mỗi ngày
#   lot       : số lượng mỗi lần nhập (hàng để lâu được)
#   shelf     : hạn sử dụng (ngày, tính từ ngày nhập)
# ---------------------------------------------------------------------------
PRODUCTS = [
    # name,                   category,          unit,   price, min,  daily, lot,  shelf
    ("Sữa tươi không đường",  "Sữa & đồ uống",  "lít",  32000, 10,   3.0,   40,   10),
    ("Sữa chua",              "Sữa & đồ uống",  "hộp",  7000,  12,   5.0,   60,   14),
    ("Sữa đặc có đường",      "Sữa & đồ uống",  "hộp",  25000, 6,    1.2,   24,   365),
    ("Nước suối 500ml",       "Sữa & đồ uống",  "chai", 5000,  24,   8.0,   96,   365),
    ("Gạo ST25",              "Lương thực",     "kg",   35000, 20,   6.0,   100,  180),
    ("Gạo nếp",               "Lương thực",     "kg",   30000, 5,    1.0,   25,   180),
    ("Mì gói",                "Lương thực",     "gói",  4500,  30,   10.0,  120,  180),
    ("Bún khô",               "Lương thực",     "gói",  15000, 5,    1.0,   20,   365),
    ("Muối i-ốt",             "Gia vị",         "kg",   8000,  2,    0.3,   10,   730),
    ("Tiêu đen xay",          "Gia vị",         "g",    400,   100,  25.0,  1000, 365),
    ("Bột ngọt",              "Gia vị",         "kg",   60000, 1,    0.15,  5,    730),
    ("Đường cát trắng",       "Gia vị",         "kg",   22000, 3,    0.8,   20,   730),
    ("Nước mắm",              "Gia vị",         "chai", 45000, 4,    0.6,   12,   540),
    ("Nước tương",            "Gia vị",         "chai", 18000, 3,    0.4,   12,   365),
    ("Dầu ăn đậu nành",       "Dầu ăn",         "lít",  55000, 5,    1.0,   20,   365),
    ("Dầu mè",                "Dầu ăn",         "chai", 65000, 2,    0.1,   6,    365),
    ("Đậu xanh",              "Đồ khô",         "kg",   45000, 2,    0.3,   10,   270),
    ("Trứng gà",              "Thực phẩm tươi", "quả",  3500,  40,   20.0,  200,  21),
]

# Mùa vụ theo tháng (Tết: tháng 1–2 bán chạy)
SEASON = {1: 1.25, 2: 1.30, 3: 0.95, 4: 0.95, 5: 1.0, 6: 1.0,
          7: 1.0, 8: 1.0, 9: 1.05, 10: 1.0, 11: 1.05, 12: 1.15}

# Cải tiến quy trình qua từng quý (chỉ số 0..3 = Q1..Q4)
RESTOCK_PROB = [0.55, 0.68, 0.80, 0.90]   # khả năng nhập ngay khi chạm mức tối thiểu
PERISHABLE_LOT = [1.30, 1.10, 0.90, 0.75]  # cỡ lô hàng mau hỏng = tiêu thụ × hạn dùng × hệ số

# Mặt hàng ngừng nhập từ ngày này (để có dữ liệu "Sắp hết"/"Hết hàng")
STOP_RESTOCK = {
    "Dầu ăn đậu nành": dt.date(2026, 10, 20),
    "Sữa đặc có đường": dt.date(2026, 10, 28),
    "Nước mắm": dt.date(2026, 11, 3),
}


def rounder(unit: str):
    if unit in COUNT_UNITS or unit == "g":
        return lambda v: float(round(v))
    return lambda v: round(v, 1)


def daily_out(unit: str, mean: float) -> float:
    """Lượng xuất trong một ngày (ngẫu nhiên quanh mức bình quân)."""
    if unit in COUNT_UNITS:
        return float(RNG.poisson(mean))
    return rounder(unit)(mean * RNG.uniform(0.4, 1.6))


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    products = pd.DataFrame(
        [(n, c, u, p, m, s, "") for n, c, u, p, m, _, _, s in PRODUCTS],
        columns=["name", "category", "unit", "price", "min_stock", "shelf_life_days", "note"],
    )

    tx = []
    for name, _cat, unit, price, min_stock, daily, lot, shelf in PRODUCTS:
        rnd = rounder(unit)
        lots: deque = deque()            # mỗi lô: [ngày nhập, số lượng còn, đơn giá nhập]
        perishable = shelf < LONG_LIFE_DAYS

        def lot_size(day: dt.date) -> float:
            if perishable:
                q = (day.month - 1) // 3
                return max(rnd(daily * shelf * PERISHABLE_LOT[q]), min_stock)
            return float(lot)

        def receive(day: dt.date, qty: float, note: str) -> None:
            in_price = round(price * RNG.uniform(0.95, 1.05), -2) if note != "Tồn đầu kỳ" else price
            lots.append([day, qty, in_price])
            tx.append((day, name, "in", qty, in_price, note))

        def consume(day: dt.date, qty: float, kind: str, note: str = "") -> None:
            """Lấy hàng theo FIFO; ghi phiếu theo từng lô (đơn giá của lô)."""
            while qty > 1e-9 and lots:
                take = min(qty, lots[0][1])
                tx.append((day, name, kind, take, price if kind == "out" else lots[0][2], note))
                lots[0][1] = round(lots[0][1] - take, 3)
                qty = round(qty - take, 3)
                if lots[0][1] <= 1e-9:
                    lots.popleft()

        receive(START, lot_size(START), "Tồn đầu kỳ")
        day = START + dt.timedelta(days=1)
        while day <= END:
            q = (day.month - 1) // 3
            # 1) Hủy các lô đã quá hạn sử dụng
            while lots and (day - lots[0][0]).days >= shelf:
                consume(day, lots[0][1], "dispose", "Hết hạn sử dụng")
            stock = round(sum(l[1] for l in lots), 3)
            # 2) Nhập hàng khi tồn thấp
            stop = STOP_RESTOCK.get(name)
            if stock <= min_stock and (stop is None or day < stop) and RNG.random() < RESTOCK_PROB[q]:
                receive(day, lot_size(day), "Nhập lô hàng")
                stock = round(sum(l[1] for l in lots), 3)
            # 3) Xuất bán trong ngày
            demand = daily_out(unit, daily * SEASON[day.month])
            qty = min(demand, stock)
            if qty > 0:
                consume(day, qty, "out")
            day += dt.timedelta(days=1)

    tx_df = pd.DataFrame(tx, columns=["date", "product", "type", "quantity", "unit_price", "note"])
    tx_df = tx_df[tx_df["quantity"] > 0]
    order = {"in": 0, "dispose": 1, "out": 2}
    tx_df["_o"] = tx_df["type"].map(order)
    tx_df = tx_df.sort_values(["date", "_o", "product"], kind="stable").drop(columns="_o")
    tx_df["date"] = pd.to_datetime(tx_df["date"]).dt.strftime("%Y-%m-%d")
    return products, tx_df


def main() -> None:
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
    os.makedirs(out_dir, exist_ok=True)
    products, tx = build()
    p_path = os.path.join(out_dir, "products.csv")
    t_path = os.path.join(out_dir, "transactions.csv")
    products.to_csv(p_path, index=False, encoding="utf-8-sig")
    tx.to_csv(t_path, index=False, encoding="utf-8-sig")
    print(f"Đã tạo {len(products)} sản phẩm  -> {p_path}")
    print(f"Đã tạo {len(tx)} giao dịch -> {t_path}")
    print(tx["type"].value_counts().to_string())


if __name__ == "__main__":
    main()
