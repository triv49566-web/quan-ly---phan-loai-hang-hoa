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


def stock_table(products: pd.DataFrame, tx: pd.DataFrame,
                window_days: int = WINDOW_DAYS) -> pd.DataFrame:
    """Bảng tồn kho: mỗi dòng một sản phẩm, thêm các cột

    quantity      tồn kho hiện tại
    value         giá trị tồn = tồn kho × đơn giá
    out_window    lượng xuất trong `window_days` ngày gần nhất
    days_cover    số ngày còn đủ dùng = tồn kho / tiêu thụ bình quân ngày
    status        Đủ hàng / Sắp hết / Hết hàng
    """
    df = products.copy()
    if tx.empty:
        qty = pd.Series(dtype=float)
        out_w = pd.Series(dtype=float)
    else:
        qty = signed(tx).groupby(tx["product_id"]).sum()
        # Mốc tính = ngày giao dịch gần nhất (ổn định cả khi dùng dữ liệu mẫu cũ)
        as_of = tx["date"].max()
        recent = tx[(tx["type"] == TX_OUT) &
                    (tx["date"] > as_of - pd.Timedelta(days=window_days))]
        out_w = recent.groupby("product_id")["quantity"].sum()

    df["quantity"] = df["id"].map(qty).fillna(0.0).round(3)
    df["value"] = df["quantity"] * df["price"]
    df["out_window"] = df["id"].map(out_w).fillna(0.0).round(3)
    avg_daily = (df["out_window"] / window_days).replace(0, np.nan)
    df["days_cover"] = (df["quantity"] / avg_daily).round(0)
    df["status"] = [evaluate_stock(q, m) for q, m in zip(df["quantity"], df["min_stock"])]
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
