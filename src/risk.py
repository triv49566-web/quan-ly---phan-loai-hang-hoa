# -*- coding: utf-8 -*-
"""
Quản lý rủi ro tồn kho: nhận diện → đánh giá (khả năng × mức ảnh hưởng) → biện pháp.

Mức rủi ro = Khả năng xảy ra (1–5) × Mức ảnh hưởng (1–5)
  ≥ 15 : Cao        → xử lý ngay trong ngày
  8–14 : Trung bình → xử lý trong tuần
  < 8  : Thấp       → theo dõi
"""

from __future__ import annotations

import math

import pandas as pd

from . import inventory
from .catalog import LONG_LIFE_DAYS, near_expiry_days

HIGH, MEDIUM, LOW = "Cao", "Trung bình", "Thấp"
LEVELS = [HIGH, MEDIUM, LOW]

RISK_TYPES = {
    "out": dict(name="Hết hàng", impact=4,
                action="Lập phiếu nhập ngay; báo nhà cung cấp giao gấp."),
    "low": dict(name="Dưới mức dự trữ", impact=3,
                action="Đặt hàng trong ngày để không bị hết hàng."),
    "expired": dict(name="Hàng quá hạn còn trong kho", impact=5,
                    action="Tách riêng và lập phiếu hủy hàng ngay; không bán."),
    "near": dict(name="Hàng cận hạn", impact=3,
                 action="Ưu tiên bán trước (nhập trước – xuất trước), cân nhắc giảm giá."),
    "slow": dict(name="Tồn đọng, bán chậm", impact=2,
                 action="Tạm ngừng nhập, giảm lượng đặt lần sau, bán giảm giá."),
}


def level_of(score: int) -> str:
    return HIGH if score >= 15 else MEDIUM if score >= 8 else LOW


def register(products: pd.DataFrame, tx: pd.DataFrame, date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Danh sách rủi ro tại ngày `date` (mặc định: ngày có giao dịch gần nhất)."""
    if tx.empty:
        return pd.DataFrame()
    date = (pd.Timestamp(date) if date is not None else tx["date"].max()).normalize()
    stock = inventory.stock_table(products, tx[tx["date"] <= date])
    lots = inventory.lots_at(products, tx, date)
    rows = []

    def add(r, kind, likelihood, detail, qty=None):
        impact = RISK_TYPES[kind]["impact"]
        # Hàng thiết yếu mau hỏng / bán chạy: ảnh hưởng nặng hơn 1 bậc
        if kind in ("out", "low") and r["shelf_life_days"] < LONG_LIFE_DAYS:
            impact = min(5, impact + 1)
        score = likelihood * impact
        rows.append(dict(product_id=r["id"], product=r["name"], category=r["category"],
                         risk=RISK_TYPES[kind]["name"], kind=kind, likelihood=likelihood,
                         impact=impact, score=score, level=level_of(score), detail=detail,
                         action=RISK_TYPES[kind]["action"],
                         value=(qty if qty is not None else 0) * r["price"]))

    for _, r in stock.iterrows():
        qty, mn, unit = float(r["quantity"]), float(r["rop"]), r["unit"]
        days = r["days_cover"]
        days = None if days is None or (isinstance(days, float) and math.isnan(days)) else float(days)
        if qty <= 0:
            add(r, "out", 5, f"Tồn 0 {unit}, điểm đặt hàng {mn:g} {unit}")
        elif qty <= mn:
            likelihood = 5 if days is not None and days <= 2 else 4 if days is not None and days <= 5 else 3
            cover = f", đủ bán ~{days:.0f} ngày" if days is not None else ""
            add(r, "low", likelihood, f"Còn {qty:g} {unit} ≤ điểm đặt hàng (ROP) {mn:g} {unit}{cover}", qty)
        if days is not None and days > 60:
            add(r, "slow", 4 if days > 120 else 3, f"Còn {qty:g} {unit}, cần ~{days:.0f} ngày mới bán hết", qty)
        elif days is None and qty > 0:
            add(r, "slow", 3, f"Còn {qty:g} {unit} nhưng 30 ngày qua không bán được", qty)

        mine = lots[lots["product_id"] == r["id"]]
        expired = mine[mine["expired"]]
        if not expired.empty:
            q = float(expired["qty"].sum())
            add(r, "expired", 5, f"{q:g} {unit} đã quá hạn {int(-expired['days_left'].min())} ngày", q)
        near = mine[mine["near"]]
        if not near.empty:
            q = float(near["qty"].sum())
            left = int(near["days_left"].min())
            likelihood = 5 if left <= 1 else 4 if left <= near_expiry_days(r["shelf_life_days"]) / 2 else 3
            add(r, "near", likelihood, f"{q:g} {unit} còn {left} ngày là hết hạn", q)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    order = {HIGH: 0, MEDIUM: 1, LOW: 2}
    return df.sort_values(["level", "score"], key=lambda s: s.map(order) if s.name == "level" else -s)
