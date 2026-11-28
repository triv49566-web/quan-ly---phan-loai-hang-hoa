# -*- coding: utf-8 -*-
"""
Các phép tính tồn kho và báo cáo, từ danh sách sản phẩm + lịch sử giao dịch.

Tồn kho KHÔNG được lưu trực tiếp mà luôn tính lại từ giao dịch:
    tồn kho = tổng nhập − tổng xuất
Nhờ vậy số liệu luôn khớp với lịch sử và không bị "lệch sổ".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .catalog import POSITIVE_TYPES, TX_IN, TX_OUT, UNCATEGORIZED, evaluate_stock

WINDOW_DAYS = 30  # số ngày dùng để tính mức tiêu thụ bình quân
SERVICE_Z = 1.65  # hệ số an toàn ứng với mức phục vụ 95%
REVIEW_DAYS = 7   # đặt thêm đủ bán 7 ngày sau khi về tới điểm đặt hàng
COUNT_UNITS = {"gói", "chai", "hộp", "lon", "túi", "quả", "cái"}


def reorder_point(daily_mean: float, daily_std: float, lead_days: float, min_stock: float) -> tuple[float, float]:
    """(tồn kho an toàn SS, điểm đặt hàng ROP).

    SS  = z × σ × √L
    ROP = d × L + SS
    d, σ: lượng xuất bình quân và độ lệch chuẩn mỗi ngày (30 ngày gần nhất); L: thời gian chờ giao.
    Chưa có lịch sử bán (d = 0) thì dùng mức tồn tối thiểu cũ.
    """
    if daily_mean <= 0:
        return 0.0, float(min_stock)
    ss = SERVICE_Z * daily_std * np.sqrt(max(lead_days, 0))
    return ss, daily_mean * lead_days + ss


def stock_table(products: pd.DataFrame, tx: pd.DataFrame,
                window_days: int = WINDOW_DAYS) -> pd.DataFrame:
    """Bảng tồn kho: mỗi dòng một sản phẩm, thêm các cột

    quantity      tồn kho hiện tại
    value         giá trị tồn = tồn kho × đơn giá
    out_window    lượng xuất trong `window_days` ngày gần nhất
    daily_mean    d: xuất bình quân / ngày;  daily_std  σ: độ lệch chuẩn / ngày
    safety_stock  tồn kho an toàn SS = z·σ·√L
    rop           điểm đặt hàng ROP = d·L + SS
    order_qty     gợi ý số lượng đặt = ROP + d × 7 − tồn (khi tồn ≤ ROP)
    days_cover    số ngày còn đủ dùng = tồn kho / tiêu thụ bình quân ngày
    status        Đủ hàng / Sắp hết (≤ ROP) / Hết hàng
    """
    df = products.copy()
    if tx.empty:
        qty = pd.Series(dtype=float)
        out_w = pd.Series(dtype=float)
        mean = std = pd.Series(dtype=float)
    else:
        qty = signed(tx).groupby(tx["product_id"]).sum()
        # Mốc tính = ngày giao dịch gần nhất (ổn định cả khi dùng dữ liệu mẫu cũ)
        as_of = tx["date"].max()
        recent = tx[(tx["type"] == TX_OUT) &
                    (tx["date"] > as_of - pd.Timedelta(days=window_days))]
        out_w = recent.groupby("product_id")["quantity"].sum()
        days = pd.date_range(as_of.normalize() - pd.Timedelta(days=window_days - 1), as_of.normalize())
        per_day = (recent.assign(d=recent["date"].dt.normalize())
                   .pivot_table(index="d", columns="product_id", values="quantity", aggfunc="sum")
                   .reindex(days, fill_value=0).fillna(0))
        mean, std = per_day.mean(), per_day.std(ddof=0)

    df["quantity"] = df["id"].map(qty).fillna(0.0).round(3)
    df["value"] = df["quantity"] * df["price"]
    df["out_window"] = df["id"].map(out_w).fillna(0.0).round(3)
    avg_daily = (df["out_window"] / window_days).replace(0, np.nan)
    df["days_cover"] = (df["quantity"] / avg_daily).round(0)
    df["daily_mean"] = df["id"].map(mean).fillna(0.0)
    df["daily_std"] = df["id"].map(std).fillna(0.0)
    lead = df["lead_time_days"] if "lead_time_days" in df else pd.Series(2, index=df.index)
    ss_rop = [reorder_point(d, s, l, m) for d, s, l, m in
              zip(df["daily_mean"], df["daily_std"], lead, df["min_stock"])]
    df["safety_stock"] = [round(x[0], 1) for x in ss_rop]
    df["rop"] = [round(x[1], 1) for x in ss_rop]
    want = df["rop"] + df["daily_mean"] * REVIEW_DAYS - df["quantity"]
    whole = df["unit"].isin(COUNT_UNITS) | (df["unit"] == "g")
    df["order_qty"] = np.where(df["quantity"] <= df["rop"],
                               np.where(whole, np.ceil(want), np.ceil(want * 10) / 10), 0).clip(min=0)
    df["status"] = [evaluate_stock(q, r) for q, r in zip(df["quantity"], df["rop"])]
    return df


def abc_table(stock: pd.DataFrame, tx: pd.DataFrame, a_cut: float = 80, b_cut: float = 95) -> pd.DataFrame:
    """Phân tích ABC theo giá trị xuất: A = nhóm chiếm 80% giá trị đầu tiên, B đến 95%, C còn lại."""
    out = tx[tx["type"] == TX_OUT]
    val = (out["quantity"] * out["unit_price"]).groupby(out["product_id"]).sum()
    lines = out.groupby("product_id").size()
    df = stock.assign(out_value=stock["id"].map(val).fillna(0.0),
                      out_lines=stock["id"].map(lines).fillna(0).astype(int))
    df = df.sort_values("out_value", ascending=False).reset_index(drop=True)
    total = df["out_value"].sum() or 1
    df["share"] = df["out_value"] / total * 100
    df["cum_share"] = df["share"].cumsum()
    prev = df["cum_share"] - df["share"]
    df["abc"] = np.where(prev < a_cut, "A", np.where(prev < b_cut, "B", "C"))
    return df


def category_summary(stock: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp theo danh mục: số mặt hàng, giá trị tồn, số mặt hàng theo trạng thái."""
    if stock.empty:
        return pd.DataFrame(columns=["category", "products", "value"])
    s = stock.assign(category=stock["category"].fillna(UNCATEGORIZED))
    out = s.groupby("category").agg(products=("id", "count"), value=("value", "sum"))
    status_counts = pd.crosstab(s["category"], s["status"])
    return out.join(status_counts).fillna(0).reset_index()


def monthly_flow(tx: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """Giá trị nhập / xuất / hủy theo tháng (freq="M") hoặc theo quý (freq="Q")."""
    if tx.empty:
        return pd.DataFrame(columns=["month", "Nhập kho", "Xuất kho", "Hủy hàng"])
    period = (tx["date"].dt.year.astype(str) + "-Q" + tx["date"].dt.quarter.astype(str)
              if freq == "Q" else tx["date"].dt.strftime("%Y-%m"))
    t = tx.assign(month=period,
                  amount=tx["quantity"] * tx["unit_price"])
    pv = t.pivot_table(index="month", columns="type", values="amount",
                       aggfunc="sum", fill_value=0)
    pv = pv.rename(columns={TX_IN: "Nhập kho", TX_OUT: "Xuất kho", "dispose": "Hủy hàng"})
    for col in ("Nhập kho", "Xuất kho", "Hủy hàng"):
        if col not in pv.columns:
            pv[col] = 0.0
    return pv[["Nhập kho", "Xuất kho", "Hủy hàng"]].reset_index()


def top_consumed(stock: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top n mặt hàng xuất nhiều nhất (theo giá trị) trong cửa sổ tiêu thụ."""
    s = stock.assign(out_value=stock["out_window"] * stock["price"])
    return s[s["out_value"] > 0].nlargest(n, "out_value")


# ---------------------------------------------------------------------------
# Tồn kho theo NGÀY và theo LÔ HÀNG (dùng cho KPI, báo cáo cuối ngày, rủi ro)
# ---------------------------------------------------------------------------
def signed(tx: pd.DataFrame) -> pd.Series:
    """Số lượng có dấu: nhập / kiểm kê thừa +, xuất / hủy / kiểm kê thiếu −."""
    return tx["quantity"] * np.where(tx["type"].isin(POSITIVE_TYPES), 1.0, -1.0)


def daily_stock(products: pd.DataFrame, tx: pd.DataFrame,
                end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Bảng tồn cuối mỗi ngày: hàng = ngày, cột = id sản phẩm."""
    ids = products["id"].tolist()
    if tx.empty:
        return pd.DataFrame(columns=ids, dtype=float)
    start = tx["date"].min().normalize()
    end = (end or tx["date"].max()).normalize()
    days = pd.date_range(start, end, freq="D")
    moves = (tx.assign(q=signed(tx), d=tx["date"].dt.normalize())
             .pivot_table(index="d", columns="product_id", values="q", aggfunc="sum"))
    moves = moves.reindex(index=days, columns=ids, fill_value=0).fillna(0)
    return moves.cumsum().round(3)


def lots_at(products: pd.DataFrame, tx: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """Các lô hàng còn trong kho cuối ngày `date` (nhập trước – xuất trước).

    Cột: product_id, in_date, qty, unit_price, expiry, days_left, near (cận hạn), expired.
    """
    from .catalog import near_expiry_days

    shelf = dict(zip(products["id"], products["shelf_life_days"]))
    t = tx[tx["date"] <= date].copy()
    t["_o"] = np.where(t["type"].isin(POSITIVE_TYPES), 0, 1)
    t = t.sort_values(["date", "_o", "id"])
    rows = []
    for pid, g in t.groupby("product_id", sort=False):
        lots = []  # [ngày nhập, số lượng còn, đơn giá]
        for r in g.itertuples(index=False):
            if r.type in POSITIVE_TYPES:
                lots.append([r.date, r.quantity, r.unit_price])
                continue
            need = r.quantity
            while need > 1e-9 and lots:
                take = min(need, lots[0][1])
                lots[0][1] -= take
                need -= take
                if lots[0][1] <= 1e-9:
                    lots.pop(0)
        life = int(shelf.get(pid, 365))
        for in_date, qty, price in lots:
            expiry = in_date + pd.Timedelta(days=life)
            left = (expiry - date).days
            rows.append((pid, in_date, round(qty, 3), price, expiry, left,
                         0 <= left <= near_expiry_days(life), left < 0))
    return pd.DataFrame(rows, columns=["product_id", "in_date", "qty", "unit_price", "expiry",
                                       "days_left", "near", "expired"])


def daily_report(products: pd.DataFrame, tx: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """Báo cáo cuối ngày: tồn đầu ngày, nhập, xuất, hủy, tồn cuối, giá trị, cận hạn."""
    date = pd.Timestamp(date).normalize()
    before = tx[tx["date"] < date]
    today = tx[tx["date"].dt.normalize() == date]
    opening = signed(before).groupby(before["product_id"]).sum()
    moved = today.pivot_table(index="product_id", columns="type", values="quantity",
                              aggfunc="sum", fill_value=0)
    lots = lots_at(products, tx, date)
    near = lots[lots["near"] | lots["expired"]].groupby("product_id")["qty"].sum()
    nearest = lots.groupby("product_id")["days_left"].min()

    df = products.copy()
    df["opening"] = df["id"].map(opening).fillna(0.0).round(3)
    for col in ("in", "out", "dispose", "adj_plus", "adj_minus"):
        df[col] = df["id"].map(moved[col] if col in moved.columns else pd.Series(dtype=float)).fillna(0.0)
    df["adjust"] = (df["adj_plus"] - df["adj_minus"]).round(3)
    df["closing"] = (df["opening"] + df["in"] - df["out"] - df["dispose"] + df["adjust"]).round(3)
    df["value"] = df["closing"] * df["price"]
    df["sales_value"] = df["out"] * df["price"]
    df["near_qty"] = df["id"].map(near).fillna(0.0)
    df["days_left"] = df["id"].map(nearest)
    df["status"] = [evaluate_stock(q, m) for q, m in zip(df["closing"], df["min_stock"])]
    return df
