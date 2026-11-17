# -*- coding: utf-8 -*-
"""
Ứng dụng web quản lý & phân loại hàng hóa nhu yếu phẩm (sữa, gạo, muối,
tiêu, dầu ăn, bột ngọt, ...). Giao diện "Sổ Kho".

Chạy:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import math
import os
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import auth
from src import database as db
from src import inventory
from src.catalog import (
    IN_STOCK, LOW_STOCK, OUT_OF_STOCK, STATUSES, TX_IN, TX_LABEL, TX_OUT,
    UNCATEGORIZED, UNITS, fmt_money, fmt_qty,
)

# ---------------------------------------------------------------------------
# Thiết lập trang & bảng màu (theo bản thiết kế)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Sổ Kho", page_icon=":material/inventory_2:", layout="wide")

ACCENT = "#14532D"
INK, MUTED, LINE = "#12211C", "#4B5B54", "#DCE3DF"
OUT_COLOR = "#B45309"          # màu "Xuất kho" trên biểu đồ
FONT = "Be Vietnam Pro, Segoe UI, sans-serif"
STATUS_CLS = {IN_STOCK: "ok", LOW_STOCK: "low", OUT_OF_STOCK: "out"}
STATUS_BAR = {IN_STOCK: "#2F7D53", LOW_STOCK: "#B45309", OUT_OF_STOCK: "#7F1D13"}
COUNT_UNITS = {"gói", "chai", "hộp", "lon", "túi", "quả", "cái"}
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.svg")

CSS = """
<style>
.sk-head p { margin: 4px 0 0; color: #4B5B54; }
.sk-stats { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); }
.sk-stat { padding: 20px; border-radius: 12px; border: 1px solid #DCE3DF; background: #fff; display: flex; flex-direction: column; gap: 6px; }
.sk-stat .l { font-size: 13px; color: #4B5B54; }
.sk-stat .v { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; line-height: 1.2; }
.sk-stat .v small { font-size: 15px; font-weight: 500; }
.sk-stat.low { background: #FDF1D7; border-color: #E9C987; color: #6B3A05; }
.sk-stat.low .l { color: #6B3A05; }
.sk-stat.out { background: #7F1D13; border-color: #7F1D13; color: #fff; }
.sk-stat.out .l { color: #FBE3DF; }
.sk-card { background: #fff; border: 1px solid #DCE3DF; border-radius: 12px; }
.sk-card h3 { margin: 0; padding: 0; font-size: 17px; font-weight: 600; }
.sk-pad { padding: 20px 24px; display: flex; flex-direction: column; gap: 14px; }
.sk-needs { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); }
.sk-need { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; border-radius: 8px; background: #F3F5F4; }
.sk-need b { display: block; }
.sk-sub { font-size: 13px; color: #4B5B54; }
.sk-pill { display: inline-block; padding: 4px 10px; border-radius: 999px; border: 1px solid; font-size: 12px; font-weight: 600; white-space: nowrap; }
.sk-pill.ok { background: #E4F0E8; color: #14532D; border-color: #B5D3C0; }
.sk-pill.low { background: #FDF1D7; color: #6B3A05; border-color: #E9C987; }
.sk-pill.out { background: #7F1D13; color: #fff; border-color: #7F1D13; }
.sk-wrap { position: relative; overflow-x: auto; }
.sk-table { width: 100%; min-width: 760px; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: 15px; }
.sk-table th { text-align: left; font-size: 12px; color: #4B5B54; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; padding: 12px 16px; white-space: nowrap; border: 0; }
.sk-table td { padding: 14px 16px; border: 0; border-top: 1px solid #E7ECE9; vertical-align: middle; }
.sk-table th:first-child, .sk-table td:first-child { padding-left: 24px; }
.sk-table th:last-child, .sk-table td:last-child { padding-right: 24px; }
.sk-table td b { white-space: nowrap; }
.sk-table .r { text-align: right; white-space: nowrap; }
.sk-table .m { color: #4B5B54; white-space: nowrap; }
.sk-meter { display: flex; flex-direction: column; gap: 6px; min-width: 200px; }
.sk-meter .top { display: flex; justify-content: space-between; gap: 8px; }
.sk-bar { position: relative; height: 6px; border-radius: 3px; background: #E7ECE9; }
.sk-bar i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; }
.sk-bar::after { content: ""; position: absolute; left: 25%; top: -3px; bottom: -3px; width: 2px; background: #12211C; }
.sk-note { margin: 0; padding: 14px 24px; border-top: 1px solid #DCE3DF; font-size: 13px; color: #4B5B54; }
.sk-empty { padding: 32px 24px; text-align: center; color: #4B5B54; }
.sk-preview { margin: 0; padding: 16px; border-radius: 8px; background: #F3F5F4; display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(min(130px, 100%), 1fr)); font-variant-numeric: tabular-nums; }
.sk-preview dt { font-size: 13px; color: #4B5B54; }
.sk-preview div { margin: 0; padding: 0; }
.sk-preview dd { margin: 0; font-size: 18px; font-weight: 600; }
.sk-preview dd.bad { color: #9B1C1C; }
.sk-list { list-style: none; margin: 0 !important; padding: 0 !important; font-variant-numeric: tabular-nums; }
.sk-list li { display: flex; align-items: center; gap: 14px; padding: 12px 0; border-top: 1px solid #E7ECE9; margin: 0 !important; padding-left: 0 !important; }
.sk-tag { flex: none; width: 52px; padding: 3px 0; border-radius: 6px; font-size: 12px; font-weight: 600; text-align: center; }
.sk-tag.in { background: #E4F0E8; color: #14532D; }
.sk-tag.out { background: #E7ECE9; color: #12211C; }
.sk-list .g { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.sk-list .g span { font-size: 13px; color: #4B5B54; }
[class*="st-key-card"] { background: #FFFFFF; }
</style>
"""


def _secret_admin() -> tuple[str | None, str | None]:
    """Tài khoản quản trị đầu tiên lấy từ .streamlit/secrets.toml (mục [auth]), nếu có."""
    try:
        cfg = st.secrets.get("auth", {})
        return cfg.get("admin_username"), cfg.get("admin_password")
    except Exception:  # chưa có file secrets
        return None, None


@st.cache_resource
def _init() -> bool:
    db.init_db()
    with db.connect() as c:
        auth.init(c)
        auth.ensure_admin_from_secrets(c, *_secret_admin())
    return True


_init()
conn = db.connect()
st.html(CSS)


def notify(msg: str, icon: str = ":material/check_circle:") -> None:
    """Lưu thông báo để hiển thị sau khi trang tải lại."""
    st.session_state["_flash"] = (msg, icon)


if "_flash" in st.session_state:
    _msg, _icon = st.session_state.pop("_flash")
    st.toast(_msg, icon=_icon)


# ===========================================================================
# ĐĂNG NHẬP
# ===========================================================================
MAX_TRIES = 5          # sai quá số lần này thì phải chờ
LOCK_SECONDS = 60
LOGO_DARK = """<svg aria-hidden="true" width="40" height="40" viewBox="0 0 32 32" fill="none"
stroke="#14532D" stroke-width="2" stroke-linejoin="round"><path d="M4 11 16 5l12 6v11l-12 6-12-6z"/>
<path d="M4 11l12 6 12-6M16 17v11"/></svg>"""


def page_login() -> None:
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.html(f"""<div style="display:flex;align-items:center;gap:12px;margin:48px 0 8px">{LOGO_DARK}
<div><div style="font-size:22px;font-weight:700;letter-spacing:-0.01em">Sổ Kho</div>
<div style="font-size:13px;color:{MUTED}">Nhu yếu phẩm hằng ngày</div></div></div>""")
        with st.container(border=True, key="card_login"):
            if auth.count_users(conn) == 0:
                _first_admin_form()
            else:
                _login_form()


def _first_admin_form() -> None:
    st.markdown("#### Tạo tài khoản quản trị")
    st.caption("Chưa có tài khoản nào. Tài khoản đầu tiên sẽ là quản trị viên, "
               "có quyền thêm tài khoản cho người khác.")
    with st.form("first_admin", border=False):
        name = st.text_input("Họ tên")
        username = st.text_input("Tên tài khoản", placeholder="ví dụ: quanly")
        pw = st.text_input("Mật khẩu", type="password", help=f"Ít nhất {auth.MIN_PASSWORD} ký tự.")
        pw2 = st.text_input("Nhập lại mật khẩu", type="password")
        if st.form_submit_button("Tạo tài khoản và vào trang", type="primary", width="stretch"):
            try:
                uid = auth.create_user(conn, username, pw, name, is_admin=True, confirm=pw2)
                st.session_state["uid"] = uid
                notify("Đã tạo tài khoản quản trị.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _login_form() -> None:
    st.markdown("#### Đăng nhập")
    now = dt.datetime.now().timestamp()
    locked_until = st.session_state.get("lock_until", 0)
    with st.form("login", border=False):
        username = st.text_input("Tài khoản", autocomplete="username")
        pw = st.text_input("Mật khẩu", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Đăng nhập", type="primary", width="stretch")
    if submitted:
        if now < locked_until:
            st.error(f"Bạn đã nhập sai {MAX_TRIES} lần. Thử lại sau {int(locked_until - now) + 1} giây.")
            return
        user = auth.authenticate(conn, username, pw)
        if user is None:
            tries = st.session_state.get("tries", 0) + 1
            st.session_state["tries"] = tries
            if tries >= MAX_TRIES:
                st.session_state["tries"] = 0
                st.session_state["lock_until"] = now + LOCK_SECONDS
                st.error(f"Sai tài khoản hoặc mật khẩu {MAX_TRIES} lần. Vui lòng chờ {LOCK_SECONDS} giây.")
            else:
                st.error("Sai tài khoản hoặc mật khẩu.")
            return
        st.session_state.pop("tries", None)
        st.session_state.pop("lock_until", None)
        st.session_state["uid"] = user["id"]
        notify(f"Xin chào, {user['full_name']}!")
        st.rerun()
    st.caption("Quên mật khẩu? Nhờ quản trị viên đặt lại ở trang Tài khoản.")


USER = auth.get_user(conn, st.session_state["uid"]) if st.session_state.get("uid") else None
if USER is None:
    st.session_state.pop("uid", None)
    st.navigation([st.Page(page_login, title="Đăng nhập", icon=":material/lock:",
                           url_path="dang-nhap")], position="hidden").run()
    st.stop()

st.logo(LOGO, size="large")

cats = db.categories_df(conn)
products = db.products_df(conn)
tx = db.transactions_df(conn)
stock = inventory.stock_table(products, tx)
stock["category"] = stock["category"].fillna(UNCATEGORIZED)
tx["category"] = tx["category"].fillna(UNCATEGORIZED)
AS_OF = f"{tx['date'].max():%d/%m/%Y}" if not tx.empty else "–"


# ---------------------------------------------------------------------------
# Hàm vẽ dùng chung
# ---------------------------------------------------------------------------
def page_head(title: str, subtitle: str, link: tuple | None = None) -> None:
    if link:
        left, right = st.columns([2, 1], vertical_alignment="bottom")
    else:
        left, right = st.container(), None
    with left:
        st.html(f'<div class="sk-head"><h1 style="margin:0;padding:0;font-size:30px;'
                f'letter-spacing:-0.02em">{escape(title)}</h1><p>{escape(subtitle)}</p></div>')
    if right is not None:
        with right.container(horizontal=True, horizontal_alignment="right"):
            if st.button(link[1], type="primary", icon=":material/add:"):
                st.switch_page(link[0])


def pill(status: str) -> str:
    return f'<span class="sk-pill {STATUS_CLS[status]}">{escape(status)}</span>'


def days_text(r) -> str:
    d = r["days_cover"]
    if r["quantity"] <= 0 or d is None or (isinstance(d, float) and math.isnan(d)):
        return "–"
    return f"{int(d)} ngày"


def plot_layout(fig: go.Figure, title: str, height: int = 340, **kw) -> go.Figure:
    """Tiêu đề in bằng st.markdown (tự xuống dòng), chú thích nằm dưới biểu đồ."""
    st.markdown(f"#### {title}")
    fig.update_layout(height=height, font=dict(family=FONT, color=INK), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", margin=dict(l=8, r=8, t=8, b=8),
                      legend=dict(orientation="h", y=-0.22, x=0, xanchor="left"), **kw)
    fig.update_xaxes(gridcolor="#E7ECE9", linecolor=LINE)
    fig.update_yaxes(gridcolor="#E7ECE9", linecolor=LINE)
    return fig


# ===========================================================================
# TRANG 1 – TỒN KHO
# ===========================================================================
def page_stock() -> None:
    n_cats = stock["category"].nunique()
    page_head("Tồn kho", f"Tính đến {AS_OF} · {len(stock)} mặt hàng trong {n_cats} danh mục",
              (pg_tx, "Ghi nhập / xuất"))

    counts = {s: int((stock["status"] == s).sum()) for s in STATUSES}
    st.html(f"""
<section class="sk-stats" aria-label="Tổng quan">
<div class="sk-stat"><span class="l">Giá trị tồn kho</span><span class="v">{fmt_money(stock['value'].sum())}</span></div>
<div class="sk-stat"><span class="l">Đủ hàng</span><span class="v">{counts[IN_STOCK]} <small style="color:#4B5B54">mặt hàng</small></span></div>
<div class="sk-stat low"><span class="l">Sắp hết</span><span class="v">{counts[LOW_STOCK]} <small>mặt hàng</small></span></div>
<div class="sk-stat out"><span class="l">Hết hàng</span><span class="v">{counts[OUT_OF_STOCK]} <small>mặt hàng</small></span></div>
</section>""")

    order = {OUT_OF_STOCK: 0, LOW_STOCK: 1, IN_STOCK: 2}
    needs = stock[stock["status"] != IN_STOCK].copy()
    if not needs.empty:
        needs["_o"] = needs["status"].map(order)
        needs = needs.sort_values(["_o", "days_cover"])
        items = []
        for _, r in needs.iterrows():
            if r["quantity"] <= 0 or days_text(r) == "–":
                sub = f"tối thiểu {fmt_qty(r['min_stock'])} {r['unit']}"
            else:
                sub = f"đủ dùng {days_text(r)}"
            items.append(
                f'<div class="sk-need"><span><b>{escape(r["name"])}</b>'
                f'<span class="sk-sub">Còn {fmt_qty(r["quantity"])} {escape(r["unit"])} · {sub}</span></span>'
                f'{pill(r["status"])}</div>')
        st.html('<section class="sk-card sk-pad" aria-label="Cần nhập hàng"><h3>Cần nhập hàng</h3>'
                f'<div class="sk-needs">{"".join(items)}</div></section>')

    with st.container(border=True, key="card1"):
        head, search = st.columns([3, 2], vertical_alignment="center")
        keyword = search.text_input("Tìm sản phẩm", placeholder="Tìm theo tên, ví dụ: gạo",
                                    label_visibility="collapsed", icon=":material/search:")
        cat_names = sorted(stock["category"].unique())
        cat_count = stock["category"].value_counts()
        options = ["Tất cả"] + cat_names
        sel = st.pills("Lọc theo danh mục", options, default="Tất cả", label_visibility="collapsed",
                       format_func=lambda c: f"{c} · {len(stock) if c == 'Tất cả' else cat_count[c]}")

        view = stock if sel in (None, "Tất cả") else stock[stock["category"] == sel]
        if keyword.strip():
            view = view[view["name"].str.contains(keyword.strip(), case=False, regex=False)]
        head.markdown(f"#### Tất cả mặt hàng <span style='font-weight:400;color:{MUTED}'>({len(view)})</span>",
                      unsafe_allow_html=True)

        rows = []
        for _, r in view.iterrows():
            mn = float(r["min_stock"])
            scale = mn * 4 if mn > 0 else max(float(r["quantity"]), 1)
            bar = min(float(r["quantity"]) / scale, 1) * 100
            u = escape(r["unit"])
            rows.append(
                f'<tr><td><b>{escape(r["name"])}</b></td><td class="m">{escape(r["category"])}</td>'
                f'<td><div class="sk-meter"><div class="top"><b>{fmt_qty(r["quantity"])} {u}</b>'
                f'<span class="sk-sub">tối thiểu {fmt_qty(mn)} {u}</span></div>'
                f'<div class="sk-bar"><i style="width:{bar:.1f}%;background:{STATUS_BAR[r["status"]]}"></i></div></div></td>'
                f'<td class="r">{fmt_qty(r["price"])} đ/{u}</td><td class="r"><b>{fmt_money(r["value"])}</b></td>'
                f'<td class="r">{days_text(r)}</td><td>{pill(r["status"])}</td></tr>')
        body = "".join(rows) if rows else ""
        empty = "" if rows else '<p class="sk-empty">Không có mặt hàng nào khớp. Thử xóa từ khóa hoặc chọn “Tất cả”.</p>'
        st.html(f"""
<div class="sk-wrap"><table class="sk-table">
<thead><tr><th>Sản phẩm</th><th>Danh mục</th><th>Tồn kho so với mức tối thiểu</th>
<th class="r">Đơn giá</th><th class="r">Giá trị tồn</th><th class="r">Đủ dùng</th><th>Trạng thái</th></tr></thead>
<tbody>{body}</tbody></table>{empty}</div>
<p class="sk-note">Vạch đen trên thanh là mức tồn tối thiểu. “Đủ dùng” = tồn kho chia cho lượng xuất
bình quân mỗi ngày trong {inventory.WINDOW_DAYS} ngày gần nhất.</p>""")

        export = view[["name", "category", "unit", "quantity", "min_stock", "price",
                       "value", "out_window", "days_cover", "status"]]
        st.download_button("Tải bảng tồn kho (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                           file_name="ton_kho.csv", mime="text/csv", icon=":material/download:")


# ===========================================================================
# TRANG 2 – NHẬP / XUẤT KHO
# ===========================================================================
def page_tx() -> None:
    page_head("Nhập / Xuất kho",
              "Mỗi phiếu ghi một lần hàng vào hoặc ra khỏi kho. Tồn kho tự tính lại theo phiếu.")
    left, right = st.columns([1, 1], gap="large")

    with left, st.container(border=True, key="card2"):
        st.markdown("#### Phiếu mới")
        if stock.empty:
            st.info("Chưa có sản phẩm. Hãy thêm ở trang **Sản phẩm & danh mục**.")
            return
        by_id = stock.sort_values("name").set_index("id")
        tx_type = st.segmented_control("Loại phiếu", [TX_IN, TX_OUT], default=TX_OUT,
                                       format_func=TX_LABEL.get, label_visibility="collapsed",
                                       width="stretch") or TX_OUT
        pid = st.selectbox("Sản phẩm", by_id.index.tolist(),
                           format_func=lambda i: f"{by_id.at[i, 'name']} — còn "
                                                 f"{fmt_qty(by_id.at[i, 'quantity'])} {by_id.at[i, 'unit']}")
        p = by_id.loc[pid]
        unit, stock_qty = p["unit"], float(p["quantity"])
        a, b = st.columns(2)
        step = 1.0 if unit in COUNT_UNITS else 0.1
        qty = a.number_input(f"Số lượng ({unit})", min_value=0.0, step=step, format="%g",
                             key=f"qty_{pid}")
        price = b.number_input(f"Đơn giá (đ / {unit})", min_value=0.0, step=1000.0,
                               value=float(p["price"]), format="%g", key=f"price_{pid}")
        a, b = st.columns(2)
        tx_date = a.date_input("Ngày", value=dt.date.today(), format="DD/MM/YYYY")
        note = b.text_input("Ghi chú", placeholder="Ví dụ: bán lẻ, nhập từ NCC A")

        is_out = tx_type == TX_OUT
        over = is_out and qty > stock_qty
        after = stock_qty - qty if is_out else stock_qty + qty
        after_txt = "Không đủ" if over else f"{fmt_qty(after)} {escape(unit)}"
        st.html(f"""
<dl class="sk-preview">
<div><dt>Tồn hiện tại</dt><dd>{fmt_qty(stock_qty)} {escape(unit)}</dd></div>
<div><dt>Tồn sau phiếu</dt><dd class="{'bad' if over else ''}">{after_txt}</dd></div>
<div><dt>Thành tiền</dt><dd>{fmt_money(qty * price)}</dd></div>
</dl>""")
        if over:
            st.error(f"Không đủ hàng để xuất: kho chỉ còn {fmt_qty(stock_qty)} {unit}.")
        if st.button("Ghi nhận phiếu", type="primary", width="stretch", disabled=over or qty <= 0):
            try:
                db.add_transaction(conn, int(pid), tx_type, qty, price, tx_date, note)
                notify(f"Đã ghi: {TX_LABEL[tx_type].lower()} {fmt_qty(qty)} {unit} {p['name']}, "
                       f"thành tiền {fmt_money(qty * price)}.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with right, st.container(border=True, key="card3"):
        h, lnk = st.columns([3, 2], vertical_alignment="center")
        h.markdown("#### Giao dịch gần đây")
        lnk.page_link(pg_history, label="Xem toàn bộ lịch sử")
        items = []
        for _, t in tx.head(12).iterrows():
            items.append(
                f'<li><span class="sk-tag {t["type"]}">{"Nhập" if t["type"] == TX_IN else "Xuất"}</span>'
                f'<div class="g"><b>{escape(t["product"])}</b><span>{t["date"]:%d/%m/%Y} · '
                f'{fmt_qty(t["quantity"])} {escape(t["unit"])}</span></div>'
                f'<b style="white-space:nowrap">{fmt_money(t["quantity"] * t["unit_price"])}</b></li>')
        st.html(f'<ul class="sk-list">{"".join(items)}</ul>'
                if items else '<p class="sk-empty">Chưa có giao dịch.</p>')


# ===========================================================================
# TRANG 3 – SẢN PHẨM & DANH MỤC
# ===========================================================================
cat_options = [None] + cats["id"].tolist()
cat_name_of = dict(zip(cats["id"], cats["name"]))


def cat_label(cid):
    return UNCATEGORIZED if cid is None else cat_name_of[cid]


def page_products() -> None:
    page_head("Sản phẩm & danh mục", "Thêm mặt hàng mới, sửa thông tin hoặc sắp xếp lại danh mục.")
    left, right = st.columns([3, 2], gap="large")

    with left:
        with st.container(border=True, key="card4"):
            st.markdown("#### Thêm sản phẩm")
            with st.form("add_product", clear_on_submit=True, border=False):
                name = st.text_input("Tên sản phẩm", placeholder="Ví dụ: Gạo ST25")
                a, b = st.columns(2)
                cid = a.selectbox("Danh mục", cat_options, format_func=cat_label)
                unit = b.selectbox("Đơn vị tính", UNITS)
                a, b, c = st.columns(3)
                price = a.number_input("Đơn giá (đ)", min_value=0.0, format="%g", step=1000.0)
                min_stock = b.number_input("Tồn tối thiểu", min_value=0.0, format="%g", step=1.0)
                opening = c.number_input("Tồn đầu kỳ", min_value=0.0, format="%g", step=1.0,
                                         help="Ghi thành một phiếu nhập.")
                note = st.text_input("Ghi chú")
                if st.form_submit_button("Thêm sản phẩm", type="primary", icon=":material/add:"):
                    try:
                        db.add_product(conn, name, cid, unit, price, min_stock, note, opening)
                        notify(f"Đã thêm sản phẩm “{name.strip()}”.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

        with st.container(border=True, key="card5"):
            st.markdown("#### Sửa / xóa sản phẩm")
            if products.empty:
                st.info("Chưa có sản phẩm.")
            else:
                prod_by_id = products.set_index("id")
                eid = st.selectbox("Chọn sản phẩm", products["id"].tolist(),
                                   format_func=lambda i: prod_by_id.at[i, "name"], key="edit_sel")
                e = prod_by_id.loc[eid]
                cur_cid = None if pd.isna(e["category_id"]) else int(e["category_id"])
                with st.form(f"edit_{eid}", border=False):
                    name = st.text_input("Tên sản phẩm", value=e["name"])
                    a, b = st.columns(2)
                    cid = a.selectbox("Danh mục", cat_options, format_func=cat_label,
                                      index=cat_options.index(cur_cid))
                    unit = b.selectbox("Đơn vị tính", UNITS,
                                       index=UNITS.index(e["unit"]) if e["unit"] in UNITS else 0)
                    a, b = st.columns(2)
                    price = a.number_input("Đơn giá (đ)", min_value=0.0, format="%g", step=1000.0,
                                           value=float(e["price"]))
                    min_stock = b.number_input("Tồn tối thiểu", min_value=0.0, format="%g", step=1.0,
                                               value=float(e["min_stock"]))
                    note = st.text_input("Ghi chú", value=e["note"] or "")
                    st.caption("Số lượng tồn kho không sửa ở đây: hãy ghi phiếu nhập / xuất để sổ luôn khớp.")
                    if st.form_submit_button("Lưu thay đổi", type="primary"):
                        try:
                            db.update_product(conn, int(eid), name, cid, unit, price, min_stock, note)
                            notify(f"Đã cập nhật “{name.strip()}”.")
                            st.rerun()
                        except ValueError as err:
                            st.error(str(err))
                confirm = st.checkbox("Tôi muốn xóa sản phẩm này (kèm toàn bộ lịch sử giao dịch)",
                                      key=f"confirm_del_{eid}")
                if st.button("Xóa sản phẩm", disabled=not confirm, icon=":material/delete:"):
                    db.delete_product(conn, int(eid))
                    notify(f"Đã xóa “{e['name']}”.", ":material/delete:")
                    st.rerun()

    with right, st.container(border=True, key="card6"):
        st.markdown("#### Danh mục")
        with st.form("add_cat", clear_on_submit=True, border=False):
            cname = st.text_input("Tên danh mục mới", placeholder="Ví dụ: Đồ hộp")
            cdesc = st.text_input("Mô tả")
            if st.form_submit_button("Thêm danh mục"):
                try:
                    db.add_category(conn, cname, cdesc)
                    notify(f"Đã thêm danh mục “{cname.strip()}”.")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
        items = "".join(
            f'<li><div class="g"><b>{escape(c["name"])}</b><span>{escape(c["description"] or "—")} · '
            f'{c["products"]} sản phẩm</span></div></li>' for _, c in cats.iterrows())
        st.html(f'<ul class="sk-list">{items}</ul>')
        if not cats.empty:
            did = st.selectbox("Xóa danh mục", cats["id"].tolist(), format_func=cat_label, key="del_cat")
            st.caption("Sản phẩm trong danh mục bị xóa sẽ chuyển sang “Chưa phân loại”.")
            if st.button("Xóa danh mục", icon=":material/delete:"):
                db.delete_category(conn, int(did))
                notify(f"Đã xóa danh mục “{cat_label(did)}”.", ":material/delete:")
                st.rerun()


# ===========================================================================
# TRANG 4 – BÁO CÁO
# ===========================================================================
def page_report() -> None:
    page_head("Báo cáo", f"Số liệu tính đến {AS_OF}.")
    if stock.empty:
        st.info("Chưa có dữ liệu.")
        return
    summary = inventory.category_summary(stock).sort_values("value")
    a, b = st.columns(2)

    with a, st.container(border=True, key="card7"):
        fig = go.Figure(go.Bar(
            y=summary["category"], x=summary["value"], orientation="h", marker_color=ACCENT,
            text=[fmt_money(v) for v in summary["value"]], textposition="auto"))
        st.plotly_chart(plot_layout(fig, "Giá trị tồn kho theo danh mục", xaxis_title="đ"),
                        width="stretch")

    with b, st.container(border=True, key="card8"):
        fig = go.Figure()
        for s in STATUSES:
            if s in summary.columns:
                fig.add_bar(y=summary["category"], x=summary[s], name=s, orientation="h",
                            marker_color=STATUS_BAR[s])
        st.plotly_chart(plot_layout(fig, "Trạng thái theo danh mục", barmode="stack",
                                    xaxis_title="số mặt hàng"), width="stretch")

    flow = inventory.monthly_flow(tx)
    labels = [f"Tháng {int(m[5:])}/{m[:4]}" for m in flow["month"]]
    with a, st.container(border=True, key="card9"):
        fig = go.Figure()
        fig.add_bar(x=labels, y=flow["Nhập kho"], name="Nhập kho", marker_color=ACCENT)
        fig.add_bar(x=labels, y=flow["Xuất kho"], name="Xuất kho", marker_color=OUT_COLOR)
        st.plotly_chart(plot_layout(fig, "Giá trị nhập / xuất theo tháng", barmode="group",
                                    yaxis_title="đ"), width="stretch")

    top = inventory.top_consumed(stock).iloc[::-1]
    with b, st.container(border=True, key="card10"):
        fig = go.Figure(go.Bar(
            y=top["name"], x=top["out_window"] * top["price"], orientation="h",
            marker_color="#1D4ED8",
            text=[f"{fmt_qty(q)} {u}" for q, u in zip(top["out_window"], top["unit"])],
            textposition="auto"))
        st.plotly_chart(plot_layout(fig, f"Xuất nhiều nhất trong {inventory.WINDOW_DAYS} ngày (theo giá trị)",
                                    xaxis_title="đ"), width="stretch")


# ===========================================================================
# TRANG 5 – LỊCH SỬ GIAO DỊCH
# ===========================================================================
def page_history() -> None:
    if tx.empty:
        page_head("Lịch sử giao dịch", "Chưa có giao dịch.")
        return
    head_slot = st.empty()
    with st.container(border=True, key="card11"):
        a, b, c, d = st.columns([2, 1, 1, 2])
        q = a.text_input("Sản phẩm", placeholder="Tìm theo tên")
        types = b.selectbox("Loại", ["", TX_IN, TX_OUT],
                            format_func=lambda t: "Tất cả" if not t else TX_LABEL[t])
        cat = c.selectbox("Danh mục", [""] + sorted(tx["category"].unique()),
                          format_func=lambda x: x or "Tất cả")
        dmin, dmax = tx["date"].min().date(), tx["date"].max().date()
        rng = d.date_input("Khoảng thời gian", value=(dmin, dmax), format="DD/MM/YYYY")

        h = tx
        if types:
            h = h[h["type"] == types]
        if cat:
            h = h[h["category"] == cat]
        if q.strip():
            h = h[h["product"].str.contains(q.strip(), case=False, regex=False)]
        if isinstance(rng, tuple) and len(rng) == 2:
            h = h[(h["date"].dt.date >= rng[0]) & (h["date"].dt.date <= rng[1])]

        out = pd.DataFrame({
            "Ngày": h["date"].dt.strftime("%d/%m/%Y"),
            "Loại": h["type"].map(TX_LABEL),
            "Sản phẩm": h["product"],
            "Danh mục": h["category"],
            "Số lượng": h["quantity"],
            "Đơn vị": h["unit"],
            "Đơn giá": h["unit_price"],
            "Thành tiền": h["quantity"] * h["unit_price"],
            "Ghi chú": h["note"],
        })
        st.dataframe(out, hide_index=True, width="stretch", height=520, column_config={
            "Số lượng": st.column_config.NumberColumn(format="localized"),
            "Đơn giá": st.column_config.NumberColumn(format="localized"),
            "Thành tiền": st.column_config.NumberColumn(format="localized"),
        })
        st.download_button("Tải CSV", out.to_csv(index=False).encode("utf-8-sig"),
                           file_name="lich_su_giao_dich.csv", mime="text/csv",
                           icon=":material/download:")

    total_in = out.loc[h["type"] == TX_IN, "Thành tiền"].sum()
    total_out = out.loc[h["type"] == TX_OUT, "Thành tiền"].sum()
    with head_slot.container():
        page_head("Lịch sử giao dịch", f"{len(out)} giao dịch · Nhập {fmt_money(total_in)} · "
                                       f"Xuất {fmt_money(total_out)}")


# ===========================================================================
# TRANG 6 – TÀI KHOẢN
# ===========================================================================
def page_account() -> None:
    page_head("Tài khoản", f"{USER['full_name']} · {USER['username']}"
              + (" · quản trị viên" if USER["is_admin"] else ""))
    left, right = st.columns([1, 1], gap="large")

    with left, st.container(border=True, key="card_pw"):
        st.markdown("#### Đổi mật khẩu")
        with st.form("change_pw", clear_on_submit=True, border=False):
            old = st.text_input("Mật khẩu hiện tại", type="password", autocomplete="current-password")
            new = st.text_input("Mật khẩu mới", type="password", autocomplete="new-password",
                                help=f"Ít nhất {auth.MIN_PASSWORD} ký tự.")
            new2 = st.text_input("Nhập lại mật khẩu mới", type="password", autocomplete="new-password")
            if st.form_submit_button("Đổi mật khẩu", type="primary"):
                try:
                    auth.change_password(conn, USER["id"], old, new, new2)
                    notify("Đã đổi mật khẩu.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    if not USER["is_admin"]:
        return

    with right, st.container(border=True, key="card_newuser"):
        st.markdown("#### Thêm tài khoản")
        with st.form("new_user", clear_on_submit=True, border=False):
            name = st.text_input("Họ tên")
            username = st.text_input("Tên tài khoản", placeholder="ví dụ: nhanvien1")
            pw = st.text_input("Mật khẩu", type="password", autocomplete="new-password",
                               help=f"Ít nhất {auth.MIN_PASSWORD} ký tự. Người dùng tự đổi sau khi đăng nhập.")
            is_admin = st.checkbox("Quản trị viên (được quản lý tài khoản)")
            if st.form_submit_button("Thêm tài khoản", type="primary", icon=":material/person_add:"):
                try:
                    auth.create_user(conn, username, pw, name, is_admin=is_admin)
                    notify(f"Đã thêm tài khoản “{auth.normalize_username(username)}”.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with st.container(border=True, key="card_users"):
        st.markdown("#### Danh sách tài khoản")
        users = auth.users_df(conn)
        st.dataframe(pd.DataFrame({
            "Tài khoản": users["username"], "Họ tên": users["full_name"],
            "Vai trò": users["is_admin"].map({1: "Quản trị viên", 0: "Nhân viên"}),
            "Ngày tạo": users["created_at"],
        }), hide_index=True, width="stretch")

        others = users[users["id"] != USER["id"]]
        if others.empty:
            return
        by_id = others.set_index("id")
        a, b = st.columns(2, vertical_alignment="bottom")
        uid = a.selectbox("Chọn tài khoản", by_id.index.tolist(),
                          format_func=lambda i: f"{by_id.at[i, 'username']} — {by_id.at[i, 'full_name'] or ''}")
        with b.popover("Đặt lại mật khẩu", icon=":material/key:"):
            with st.form(f"reset_{uid}", border=False):
                newpw = st.text_input("Mật khẩu mới", type="password", autocomplete="new-password")
                if st.form_submit_button("Đặt lại", type="primary"):
                    try:
                        auth.reset_password(conn, int(uid), newpw)
                        notify(f"Đã đặt lại mật khẩu cho “{by_id.at[uid, 'username']}”.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
        confirm = st.checkbox(f"Tôi muốn xóa tài khoản “{by_id.at[uid, 'username']}”", key=f"del_user_{uid}")
        if st.button("Xóa tài khoản", disabled=not confirm, icon=":material/person_remove:"):
            try:
                auth.delete_user(conn, int(uid), USER["id"])
                notify(f"Đã xóa tài khoản “{by_id.at[uid, 'username']}”.", ":material/delete:")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ---------------------------------------------------------------------------
# Điều hướng (thanh bên)
# ---------------------------------------------------------------------------
pg_stock = st.Page(page_stock, title="Tồn kho", icon=":material/inventory_2:",
                   url_path="ton-kho", default=True)
pg_tx = st.Page(page_tx, title="Nhập / Xuất kho", icon=":material/swap_vert:", url_path="nhap-xuat")
pg_products = st.Page(page_products, title="Sản phẩm & danh mục", icon=":material/sell:",
                      url_path="san-pham")
pg_report = st.Page(page_report, title="Báo cáo", icon=":material/bar_chart:", url_path="bao-cao")
pg_history = st.Page(page_history, title="Lịch sử giao dịch", icon=":material/receipt_long:",
                     url_path="lich-su")

pg_account = st.Page(page_account, title="Tài khoản", icon=":material/manage_accounts:",
                     url_path="tai-khoan")

with st.sidebar:
    st.caption(f"Đang đăng nhập: **{USER['full_name']}** ({USER['username']})"
               + (" · quản trị" if USER["is_admin"] else ""))
    if st.button("Đăng xuất", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()

nav = st.navigation([pg_stock, pg_tx, pg_products, pg_report, pg_history, pg_account])
nav.run()
