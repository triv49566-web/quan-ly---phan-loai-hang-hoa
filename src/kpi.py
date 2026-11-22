# -*- coding: utf-8 -*-
"""
KPI đánh giá QUY TRÌNH QUẢN LÝ KHO (và người phụ trách kho) theo từng quý.

Khung đánh giá:
  1. Đối tượng : Quy trình quản lý kho nhu yếu phẩm
  2. Tiêu chí  → Chỉ số (Index) → Tiêu chuẩn (mục tiêu / ngưỡng cảnh báo)
  3. Dữ liệu   : lịch sử phiếu nhập / xuất / hủy, danh mục sản phẩm (hạn dùng, mức dự trữ)

Mỗi chỉ số có: tiêu chí (group), tên, đơn vị, công thức, nguồn dữ liệu,
hướng tốt (cao/thấp), mục tiêu (target), ngưỡng cảnh báo (warn), trọng số.
Muốn đổi tiêu chuẩn hoặc trọng số → chỉ cần sửa KPI_DEFS.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import inventory
from .catalog import TX_DISPOSE, TX_IN, TX_OUT

OBJECT = "Quy trình quản lý kho nhu yếu phẩm"

GOOD, WARN, BAD = "Đạt", "Cảnh báo", "Chưa đạt"
STATUS_POINTS = {GOOD: 1.0, WARN: 0.6, BAD: 0.2}   # tỷ lệ điểm nhận được theo trọng số

SLOW_DAYS = 60          # tồn > 60 ngày bán mới hết  → hàng tồn đọng
RESTOCK_WITHIN = 2      # chạm mức dự trữ phải có phiếu nhập trong ≤ 2 ngày

CRITERIA = ["Bảo đảm dự trữ", "Chất lượng bảo quản", "Hiệu suất sử dụng vốn", "Tuân thủ quy trình"]

KPI_DEFS = {
    "in_stock": dict(
        group="Bảo đảm dự trữ", label="Tỷ lệ ngày còn hàng", unit="%", fmt="pct",
        higher=True, target=98, warn=95, weight=20,
        formula="Số (ngày × mặt hàng) có tồn > 0 ÷ tổng số (ngày × mặt hàng) × 100",
        data="Tồn cuối mỗi ngày, tính từ phiếu nhập / xuất / hủy"),
    "reserve": dict(
        group="Bảo đảm dự trữ", label="Tỷ lệ đạt mức dự trữ", unit="%", fmt="pct",
        higher=True, target=90, warn=80, weight=15,
        formula="Số (ngày × mặt hàng) có tồn > mức tối thiểu ÷ tổng số (ngày × mặt hàng) × 100",
        data="Tồn cuối mỗi ngày, mức tồn tối thiểu của từng sản phẩm"),
    "stockouts": dict(
        group="Bảo đảm dự trữ", label="Số lần hết hàng", unit="lần", fmt="int",
        higher=False, target=2, warn=5, weight=10,
        formula="Số lần một mặt hàng chuyển từ còn hàng sang hết hàng trong quý",
        data="Tồn cuối mỗi ngày"),
    "expiry_loss": dict(
        group="Chất lượng bảo quản", label="Tỷ lệ hao hụt do hết hạn", unit="%", fmt="pct",
        higher=False, target=1, warn=3, weight=15,
        formula="Giá trị hàng hủy ÷ giá trị hàng nhập trong quý × 100",
        data="Phiếu hủy hàng, phiếu nhập kho"),
    "near_expiry": dict(
        group="Chất lượng bảo quản", label="Tỷ lệ hàng cận hạn cuối quý", unit="%", fmt="pct",
        higher=False, target=5, warn=10, weight=10,
        formula="Giá trị tồn của các lô còn ≤ 20% hạn dùng ÷ giá trị tồn cuối quý × 100",
        data="Lô hàng còn trong kho (nhập trước – xuất trước), hạn dùng sản phẩm"),
    "turnover": dict(
        group="Hiệu suất sử dụng vốn", label="Vòng quay tồn kho (quy năm)", unit="vòng", fmt="num",
        higher=True, target=24, warn=15, weight=10,
        formula="Giá trị xuất trong quý ÷ giá trị tồn bình quân × (365 ÷ số ngày của quý)",
        data="Phiếu xuất kho, tồn cuối mỗi ngày, đơn giá"),
    "slow_moving": dict(
        group="Hiệu suất sử dụng vốn", label="Tỷ lệ hàng tồn đọng", unit="%", fmt="pct",
        higher=False, target=10, warn=20, weight=10,
        formula=f"Giá trị tồn của mặt hàng cần > {SLOW_DAYS} ngày mới bán hết ÷ giá trị tồn cuối quý × 100",
        data="Tồn cuối quý, lượng xuất 30 ngày cuối quý"),
    "timely_restock": dict(
        group="Tuân thủ quy trình", label="Tỷ lệ nhập hàng kịp thời", unit="%", fmt="pct",
        higher=True, target=90, warn=75, weight=10,
        formula=f"Số lần chạm mức dự trữ có phiếu nhập trong ≤ {RESTOCK_WITHIN} ngày ÷ tổng số lần chạm × 100",
        data="Tồn cuối mỗi ngày, phiếu nhập kho"),
}

GRADES = [(85, "A", "Tốt"), (70, "B", "Khá"), (50, "C", "Trung bình"), (0, "D", "Cần cải thiện")]


# ---------------------------------------------------------------------------
# Đánh giá & định dạng
# ---------------------------------------------------------------------------
def evaluate(key: str, value: float) -> str:
    d = KPI_DEFS[key]
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return BAD
    if d["higher"]:
        return GOOD if value >= d["target"] else WARN if value >= d["warn"] else BAD
    return GOOD if value <= d["target"] else WARN if value <= d["warn"] else BAD


def fmt_value(key: str, value: float) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    f = KPI_DEFS[key]["fmt"]
    if f == "pct":
        return f"{value:.1f}%".replace(".", ",")
    if f == "int":
        return f"{int(round(value))}"
    return f"{value:.1f}".replace(".", ",")


def standard_text(key: str) -> str:
    d = KPI_DEFS[key]
    sign_good, sign_warn = ("≥", "≥") if d["higher"] else ("≤", "≤")
    return (f"Đạt {sign_good} {fmt_value(key, d['target'])} · "
            f"Cảnh báo {sign_warn} {fmt_value(key, d['warn'])}")


def grade(score: float) -> tuple[str, str]:
    for lo, letter, text in GRADES:
        if score >= lo:
            return letter, text
    return "D", "Cần cải thiện"


# ---------------------------------------------------------------------------
# Tính KPI cho một kỳ
# ---------------------------------------------------------------------------
def quarters(tx: pd.DataFrame) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Các quý có dữ liệu: (nhãn, ngày đầu, ngày cuối có dữ liệu)."""
    if tx.empty:
        return []
    first, last = tx["date"].min().normalize(), tx["date"].max().normalize()
    out = []
    for p in pd.period_range(first, last, freq="Q"):
        start = max(p.start_time.normalize(), first)
        end = min(p.end_time.normalize(), last)
        label = f"Q{p.quarter}/{p.year}"
        if end < p.end_time.normalize():
            label += f" (đến {end:%d/%m})"
        out.append((label, start, end))
    return out


def compute(products: pd.DataFrame, tx: pd.DataFrame, start: pd.Timestamp,
            end: pd.Timestamp, daily: pd.DataFrame | None = None) -> dict:
    """Tính toàn bộ chỉ số KPI cho kỳ [start, end] (tính cả hai đầu)."""
    if daily is None:
        daily = inventory.daily_stock(products, tx)
    price = products.set_index("id")["price"].reindex(daily.columns).fillna(0)
    min_stock = products.set_index("id")["min_stock"].reindex(daily.columns).fillna(0)
    D = daily.loc[start:end]
    prev = daily.shift(1).loc[start:end].fillna(0)
    cells = D.size or 1
    period_tx = tx[(tx["date"] >= start) & (tx["date"] <= end)]
    n_days = max((end - start).days + 1, 1)

    def value_of(kind: str) -> float:
        t = period_tx[period_tx["type"] == kind]
        return float((t["quantity"] * t["unit_price"]).sum())

    r = {}
    r["in_stock"] = float((D > 1e-9).sum().sum()) / cells * 100
    r["reserve"] = float((D.gt(min_stock, axis=1)).sum().sum()) / cells * 100
    r["stockouts"] = float(((prev > 1e-9) & (D <= 1e-9)).sum().sum())

    in_value = value_of(TX_IN)
    r["expiry_loss"] = value_of(TX_DISPOSE) / in_value * 100 if in_value else 0.0

    lots = inventory.lots_at(products, tx, end)
    end_value = float((D.iloc[-1] * price).sum()) if len(D) else 0.0
    if end_value > 0 and not lots.empty:
        lot_value = lots["qty"] * lots["product_id"].map(price).fillna(0)
        r["near_expiry"] = float(lot_value[lots["near"] | lots["expired"]].sum()) / end_value * 100
    else:
        r["near_expiry"] = 0.0

    avg_value = float((D * price).sum(axis=1).mean()) if len(D) else 0.0
    out_value = float((period_tx.loc[period_tx["type"] == TX_OUT, "quantity"]
                       * period_tx.loc[period_tx["type"] == TX_OUT, "product_id"].map(price)).sum())
    r["turnover"] = out_value / avg_value * (365 / n_days) if avg_value else 0.0

    last30 = period_tx[(period_tx["type"] == TX_OUT) & (period_tx["date"] > end - pd.Timedelta(days=30))]
    daily_out = (last30.groupby("product_id")["quantity"].sum() / min(30, n_days)).reindex(daily.columns).fillna(0)
    stock_end = D.iloc[-1] if len(D) else pd.Series(0.0, index=daily.columns)
    cover = stock_end / daily_out.replace(0, np.nan)
    slow = (cover > SLOW_DAYS) | ((daily_out == 0) & (stock_end > 0))
    r["slow_moving"] = float((stock_end[slow] * price[slow]).sum()) / end_value * 100 if end_value else 0.0

    # Nhập kịp thời: mỗi lần tồn từ trên mức dự trữ rơi xuống ≤ mức dự trữ
    hits = (prev.gt(min_stock, axis=1)) & (D.le(min_stock, axis=1))
    ins = tx[tx["type"] == TX_IN]
    in_days = {pid: set(g["date"].dt.normalize()) for pid, g in ins.groupby("product_id")}
    total = timely = 0
    for pid in D.columns:
        for day in D.index[hits[pid].values]:
            total += 1
            window = {day + pd.Timedelta(days=k) for k in range(RESTOCK_WITHIN + 1)}
            if in_days.get(pid, set()) & window:
                timely += 1
    r["timely_restock"] = timely / total * 100 if total else 100.0
    return r


def score_of(values: dict) -> float:
    total_w = sum(d["weight"] for d in KPI_DEFS.values())
    pts = sum(d["weight"] * STATUS_POINTS[evaluate(k, values[k])] for k, d in KPI_DEFS.items())
    return pts / total_w * 100


def quarterly_table(products: pd.DataFrame, tx: pd.DataFrame) -> pd.DataFrame:
    """Mỗi dòng một quý: các chỉ số KPI + điểm tổng hợp + xếp loại."""
    daily = inventory.daily_stock(products, tx)
    rows = []
    for label, start, end in quarters(tx):
        v = compute(products, tx, start, end, daily)
        v["score"] = score_of(v)
        v["grade"] = grade(v["score"])[0]
        v["period"], v["start"], v["end"] = label, start, end
        rows.append(v)
    return pd.DataFrame(rows).set_index("period") if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Phương án cải tiến
# ---------------------------------------------------------------------------
ACTIONS = {
    "in_stock": "Rà soát mức tồn tối thiểu theo lượng bán thực tế; đặt hàng ngay khi chạm mức dự trữ, "
                "không chờ hết hàng mới nhập.",
    "reserve": "Nâng mức dự trữ cho mặt hàng bán chạy, lập lịch nhập định kỳ (ví dụ mỗi tuần) "
               "thay vì nhập khi phát hiện thiếu.",
    "stockouts": "Theo dõi cảnh báo “Sắp hết” hằng ngày trên trang Tồn kho; ký thỏa thuận giao nhanh "
                 "với nhà cung cấp cho nhóm hàng thiết yếu.",
    "expiry_loss": "Nhập hàng mau hỏng theo lô nhỏ, sát lượng bán (lô ≈ lượng bán trong 70–80% hạn dùng); "
                   "luôn xuất theo nguyên tắc nhập trước – xuất trước.",
    "near_expiry": "Ưu tiên bán / khuyến mãi các lô cận hạn; kiểm tra hạn dùng trong báo cáo cuối ngày.",
    "turnover": "Giảm lượng nhập mỗi lần cho mặt hàng bán chậm, tăng tần suất nhập để giảm vốn nằm trong kho.",
    "slow_moving": "Tạm ngừng nhập hàng tồn đọng, bán giảm giá hoặc chuyển kênh bán; xem lại nhu cầu thực tế.",
    "timely_restock": "Giao trách nhiệm kiểm tra tồn kho cuối ngày cho một người; phiếu nhập phải lập trong "
                      f"≤ {RESTOCK_WITHIN} ngày kể từ khi chạm mức dự trữ.",
}


def drivers(key: str, products: pd.DataFrame, tx: pd.DataFrame, start: pd.Timestamp,
            end: pd.Timestamp, daily: pd.DataFrame, n: int = 3) -> list[str]:
    """Các mặt hàng ảnh hưởng nhiều nhất tới một chỉ số trong kỳ."""
    names = products.set_index("id")["name"]
    price = products.set_index("id")["price"].reindex(daily.columns).fillna(0)
    min_stock = products.set_index("id")["min_stock"].reindex(daily.columns).fillna(0)
    D = daily.loc[start:end]
    t = tx[(tx["date"] >= start) & (tx["date"] <= end)]
    if key in ("in_stock", "stockouts"):
        s = (D <= 1e-9).sum()
    elif key == "reserve":
        s = D.le(min_stock, axis=1).sum()
    elif key == "expiry_loss":
        d = t[t["type"] == TX_DISPOSE]
        s = (d["quantity"] * d["unit_price"]).groupby(d["product_id"]).sum()
    elif key == "near_expiry":
        lots = inventory.lots_at(products, tx, end)
        lots = lots[lots["near"] | lots["expired"]]
        s = (lots["qty"] * lots["product_id"].map(price)).groupby(lots["product_id"]).sum()
    elif key in ("turnover", "slow_moving"):
        stock_end = D.iloc[-1] if len(D) else pd.Series(0.0, index=daily.columns)
        last30 = t[(t["type"] == TX_OUT) & (t["date"] > end - pd.Timedelta(days=30))]
        per_day = last30.groupby("product_id")["quantity"].sum().reindex(daily.columns).fillna(0) / 30
        cover = (stock_end / per_day.replace(0, np.nan)).fillna(np.inf).where(stock_end > 0, 0)
        s = cover[cover > (SLOW_DAYS if key == "slow_moving" else 15)]
    else:  # timely_restock
        s = (D.le(min_stock, axis=1)).sum()
    s = s[s > 0].sort_values(ascending=False).head(n)
    return [names.get(pid, str(pid)) for pid in s.index]


def improvement_plan(products: pd.DataFrame, tx: pd.DataFrame, row: pd.Series,
                     prev: pd.Series | None, daily: pd.DataFrame) -> list[dict]:
    """Phương án cải tiến cho các chỉ số chưa đạt / cảnh báo / đang xấu đi."""
    plans = []
    for key, d in KPI_DEFS.items():
        status = evaluate(key, row[key])
        worse = False
        if prev is not None:
            delta = row[key] - prev[key]
            worse = (delta < -1e-9) if d["higher"] else (delta > 1e-9)
        if status == GOOD and not worse:
            continue
        items = drivers(key, products, tx, row["start"], row["end"], daily)
        plans.append({
            "key": key, "label": d["label"], "group": d["group"], "status": status,
            "value": fmt_value(key, row[key]), "standard": standard_text(key),
            "priority": {BAD: "Cao", WARN: "Trung bình", GOOD: "Theo dõi"}[status],
            "items": items, "action": ACTIONS[key],
        })
    order = {"Cao": 0, "Trung bình": 1, "Theo dõi": 2}
    return sorted(plans, key=lambda p: (order[p["priority"]], -KPI_DEFS[p["key"]]["weight"]))
