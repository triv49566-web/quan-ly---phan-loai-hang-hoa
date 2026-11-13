# -*- coding: utf-8 -*-
"""
Sinh bộ dữ liệu mẫu cho ứng dụng quản lý nhu yếu phẩm.

Mô phỏng một cửa hàng / kho nhỏ trong khoảng 3,5 tháng:
  - mỗi ngày xuất bán một lượng hàng dao động quanh mức tiêu thụ bình quân
  - khi tồn kho xuống dưới mức tối thiểu thì (thường) nhập thêm một lô
  - một vài mặt hàng ngừng nhập ở cuối kỳ → xuất hiện "Sắp hết" / "Hết hàng"

Chạy:  python data/generate_sample_data.py
Kết quả: data/raw/products.csv và data/raw/transactions.csv
(Sau khi sinh lại, xóa file data/hanghoa.db để app nạp dữ liệu mới.)
"""

from __future__ import annotations

import datetime as dt
import os

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)  # cố định seed để tái lập được

START = dt.date(2026, 8, 1)
END = dt.date(2026, 11, 12)

# Đơn vị đếm theo cái/chai/gói... thì số lượng là số nguyên
COUNT_UNITS = {"gói", "chai", "hộp", "lon", "túi", "quả", "cái"}

# ---------------------------------------------------------------------------
# Danh sách sản phẩm
#   price     : đơn giá tham khảo (đ / đơn vị)
#   min_stock : mức tồn tối thiểu (dưới mức này là "Sắp hết")
#   daily     : tiêu thụ bình quân mỗi ngày
#   lot       : số lượng mỗi lần nhập hàng
# ---------------------------------------------------------------------------
PRODUCTS = [
    # name,                   category,         unit,   price, min_stock, daily, lot
    ("Sữa tươi không đường",  "Sữa & đồ uống", "lít",  32000, 10,  3.0,  40),
    ("Sữa đặc có đường",      "Sữa & đồ uống", "hộp",  25000, 6,   1.2,  24),
    ("Nước suối 500ml",       "Sữa & đồ uống", "chai", 5000,  24,  8.0,  96),
    ("Gạo ST25",              "Lương thực",    "kg",   35000, 20,  6.0,  100),
    ("Gạo nếp",               "Lương thực",    "kg",   30000, 5,   1.0,  25),
    ("Mì gói",                "Lương thực",    "gói",  4500,  30,  10.0, 120),
    ("Bún khô",               "Lương thực",    "gói",  15000, 5,   1.0,  20),
    ("Muối i-ốt",             "Gia vị",        "kg",   8000,  2,   0.3,  10),
    ("Tiêu đen xay",          "Gia vị",        "g",    400,   100, 25.0, 1000),
    ("Bột ngọt",              "Gia vị",        "kg",   60000, 1,   0.15, 5),
    ("Đường cát trắng",       "Gia vị",        "kg",   22000, 3,   0.8,  20),
    ("Nước mắm",              "Gia vị",        "chai", 45000, 4,   0.6,  12),
    ("Nước tương",            "Gia vị",        "chai", 18000, 3,   0.4,  12),
    ("Dầu ăn đậu nành",       "Dầu ăn",        "lít",  55000, 5,   1.0,  20),
    ("Dầu mè",                "Dầu ăn",        "chai", 65000, 2,   0.1,  6),
    ("Đậu xanh",              "Đồ khô",        "kg",   45000, 2,   0.3,  10),
]

# Mặt hàng ngừng nhập từ ngày này (để có dữ liệu "Sắp hết"/"Hết hàng")
STOP_RESTOCK = {
    "Dầu ăn đậu nành": dt.date(2026, 10, 20),
    "Sữa đặc có đường": dt.date(2026, 10, 28),
    "Nước mắm": dt.date(2026, 11, 3),
}


def daily_out(unit: str, mean: float) -> float:
    """Lượng xuất trong một ngày (ngẫu nhiên quanh mức bình quân)."""
    if unit in COUNT_UNITS:
        return float(RNG.poisson(mean))
    v = mean * RNG.uniform(0.4, 1.6)
    return float(round(v)) if unit == "g" else round(v, 1)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    products = pd.DataFrame(
        [(n, c, u, p, m, "") for n, c, u, p, m, _, _ in PRODUCTS],
        columns=["name", "category", "unit", "price", "min_stock", "note"],
    )

    tx = []
    for name, _cat, unit, price, min_stock, daily, lot in PRODUCTS:
        stock = float(lot)
        tx.append((START, name, "in", lot, price, "Tồn đầu kỳ"))
        day = START + dt.timedelta(days=1)
        while day <= END:
            # Nhập hàng khi tồn thấp (70% khả năng nhập ngay trong ngày)
            stop = STOP_RESTOCK.get(name)
            if stock <= min_stock and (stop is None or day < stop) and RNG.random() < 0.7:
                in_price = round(price * RNG.uniform(0.95, 1.05), -2)
                tx.append((day, name, "in", lot, in_price, "Nhập lô hàng"))
                stock += lot
            # Xuất bán trong ngày
            q = min(daily_out(unit, daily), stock)
            if q > 0:
                tx.append((day, name, "out", q, price, ""))
                stock = round(stock - q, 3)
            day += dt.timedelta(days=1)

    tx_df = pd.DataFrame(tx, columns=["date", "product", "type", "quantity",
                                      "unit_price", "note"])
    tx_df["date"] = pd.to_datetime(tx_df["date"]).dt.strftime("%Y-%m-%d")
    tx_df = tx_df.sort_values(["date", "type", "product"], kind="stable")
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


if __name__ == "__main__":
    main()
