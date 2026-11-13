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

from .catalog import TX_IN, TX_OUT, UNCATEGORIZED, evaluate_stock

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
        sign = np.where(tx["type"] == TX_IN, 1.0, -1.0)
        qty = (tx["quantity"] * sign).groupby(tx["product_id"]).sum()
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


def monthly_flow(tx: pd.DataFrame) -> pd.DataFrame:
    """Giá trị nhập / xuất theo tháng (đ). Cột: month, Nhập kho, Xuất kho."""
    if tx.empty:
        return pd.DataFrame(columns=["month", "Nhập kho", "Xuất kho"])
    t = tx.assign(month=tx["date"].dt.strftime("%Y-%m"),
                  amount=tx["quantity"] * tx["unit_price"])
    pv = t.pivot_table(index="month", columns="type", values="amount",
                       aggfunc="sum", fill_value=0)
    pv = pv.rename(columns={TX_IN: "Nhập kho", TX_OUT: "Xuất kho"})
    for col in ("Nhập kho", "Xuất kho"):
        if col not in pv.columns:
            pv[col] = 0.0
    return pv[["Nhập kho", "Xuất kho"]].reset_index()


def top_consumed(stock: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top n mặt hàng xuất nhiều nhất (theo giá trị) trong cửa sổ tiêu thụ."""
    s = stock.assign(out_value=stock["out_window"] * stock["price"])
    return s[s["out_value"] > 0].nlargest(n, "out_value")
