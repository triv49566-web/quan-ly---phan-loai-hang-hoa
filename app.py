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
from src import inventory, kpi, risk
from src.catalog import (
    IN_STOCK, LONG_LIFE, LONG_LIFE_DAYS, LOW_STOCK, OUT_OF_STOCK, SHORT_LIFE, STATUSES, TX_DISPOSE,
    TX_ADJ_MINUS, TX_ADJ_PLUS, TX_IN, TX_LABEL, TX_OUT, UNCATEGORIZED, UNITS, ZONE_COLD, ZONE_FROZEN, ZONES, fmt_money, fmt_qty,
    storage_class, zone_of,
)

st.set_page_config(page_title="Sổ Kho", page_icon=":material/inventory_2:", layout="wide")

ACCENT = "#14532D"
INK, MUTED, LINE = "#12211C", "#4B5B54", "#DCE3DF"
OUT_COLOR = "#B45309"
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
.sk-table .nowrap { white-space: nowrap; }
.sk-table.sk-compact { min-width: 0; }
.sk-compact th:first-child, .sk-compact td:first-child { padding-left: 8px; }
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
.sk-tag.dispose { background: #FBE3DF; color: #7F1D13; }
.sk-tag.adj_plus, .sk-tag.adj_minus { background: #DBEAFE; color: #1E3A8A; }
.sk-pill.neutral { background: #F3F5F4; color: #12211C; border-color: #B9C4BE; }
.sk-stat .sk-sub { margin-top: 2px; }
.sk-stat.out .sk-sub { color: #FBE3DF; }
.sk-stat.low .sk-sub { color: #6B3A05; }
.sk-table td[rowspan] { background: #F8FAF9; vertical-align: top; }
.sk-list .g { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.sk-list .g span { font-size: 13px; color: #4B5B54; }
.sk-fixed { table-layout: fixed; min-width: 1000px; }
.sk-fixed td { vertical-align: top; }
.sk-fixed th, .sk-fixed td b { white-space: normal; }
.sk-fixed .sk-lot .lt b { white-space: nowrap; }
.sk-legend { display: flex; gap: 18px; flex-wrap: wrap; font-size: 13px; color: #4B5B54; }
.sk-legend i { display: inline-block; width: 22px; height: 8px; border-radius: 4px; margin-right: 6px; vertical-align: middle; }
.sk-ztag { display: inline-block; margin-top: 4px; font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 6px; }
.sk-ztag.cold { background: #DBEAFE; color: #1E3A8A; }
.sk-ztag.dry { background: #F3F5F4; color: #12211C; border: 1px solid #DCE3DF; }
.sk-lot { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.sk-lot .lt { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #4B5B54; white-space: nowrap; }
.sk-lot .lt b { color: #12211C; }
.sk-track { height: 8px; background: #E7ECE9; border-radius: 4px; overflow: hidden; }
.sk-track i { display: block; height: 100%; border-radius: 4px; }
i.safe { background: #2F7D53; } i.first { background: #D97706; } i.near { background: #B91C1C; } i.exp { background: #4C0519; }
.sk-lot b.t-safe { color: #14532D; } .sk-lot b.t-first { color: #92400E; } .sk-lot b.t-near, .sk-lot b.t-exp { color: #9B1C1C; }
.sk-cdcell { background: #F8FAF9; }
.sk-cd { display: block; font-size: 26px; font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; margin-bottom: 2px; }
.sk-cd small { font-size: 13px; font-weight: 600; }
.sk-cd.safe { color: #14532D; } .sk-cd.first { color: #B45309; } .sk-cd.near { color: #B91C1C; } .sk-cd.exp { color: #4C0519; }
.sk-cd.none { color: #9DB8AA; }
.sk-none { font-size: 12px; color: #9B1C1C; font-weight: 600; }
.sk-pill.exp { background: #4C0519; color: #fff; border-color: #4C0519; }
.sk-people { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); }
.sk-person { padding: 20px 24px; display: flex; flex-wrap: wrap; gap: 14px 18px; align-items: center; }
.sk-person .who { flex: 1 1 200px; min-width: 0; }
.sk-person .av { flex: none; width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 20px; color: #fff; }
.sk-person .rk { font-size: 12px; font-weight: 700; color: #4B5B54; text-transform: uppercase; letter-spacing: .04em; }
.sk-person .nm { font-size: 19px; font-weight: 700; }
.sk-person .sc { text-align: right; }
.sk-person .big { font-size: 40px; font-weight: 700; line-height: 1; letter-spacing: -0.02em; }
.sk-person .big small { font-size: 15px; color: #4B5B54; font-weight: 500; }
.sk-person .gr { display: inline-block; margin-top: 6px; padding: 3px 10px; border-radius: 999px; font-weight: 700; font-size: 13px; color: #fff; }
.sk-person .chips { flex-basis: 100%; display: flex; gap: 8px; flex-wrap: wrap; border-top: 1px solid #E7ECE9; padding-top: 12px; }
.sk-person .rm { flex-basis: 100%; font-size: 14px; background: #F8FAF9; border-radius: 8px; padding: 10px 12px; }
.sk-up { color: #14532D; font-size: 12px; font-weight: 600; } .sk-down { color: #9B1C1C; font-size: 12px; font-weight: 600; }
[class*="st-key-card"] { background: #FFFFFF; }
</style>
"""


def _secret_auth() -> dict:
    try:
        return st.secrets.get("auth", {}) or {}
    except Exception:
        return {}


@st.cache_resource
def _init() -> bool:
    db.init_db()
    with db.connect() as c:
        auth.init(c)
        auth.sync_from_secrets(c, _secret_auth())
        db.assign_from_config(c, _secret_auth().get("assign", {}))
    return True


_init()
conn = db.connect()
st.html(CSS)


def notify(msg: str, icon: str = ":material/check_circle:") -> None:
    st.session_state["_flash"] = (msg, icon)


if "_flash" in st.session_state:
    _msg, _icon = st.session_state.pop("_flash")
    st.toast(_msg, icon=_icon)


MAX_TRIES = 5
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
        if auth.count_users(conn) > 0 and auth.count_admins(conn) == 0:
            with st.expander("Chưa có tài khoản quản trị: tạo ngay", icon=":material/admin_panel_settings:"):
                _first_admin_form()


def _first_admin_form() -> None:
    st.markdown("#### Tạo tài khoản quản trị")
    st.caption("Chưa có tài khoản quản trị nào. Tài khoản tạo ở đây là quản trị viên, "
               "có quyền sửa dữ liệu và thêm tài khoản cho người khác.")
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
STOCKTAKES = db.stocktakes_df(conn)
stock = inventory.stock_table(products, tx)
MY_PIDS = set(products["id"]) if USER["is_admin"] else set(
    products.loc[products["manager_id"] == USER["id"], "id"])
stock["category"] = stock["category"].fillna(UNCATEGORIZED)
stock["storage"] = stock["shelf_life_days"].map(storage_class)
tx["category"] = tx["category"].fillna(UNCATEGORIZED)
LOTS_NOW = inventory.lots_at(products, tx, tx["date"].max()) if not tx.empty else pd.DataFrame(
    columns=["product_id", "days_left", "near", "expired", "qty"])
NEAREST = LOTS_NOW.groupby("product_id")["days_left"].min()
names_by_id = dict(zip(products["id"], products["name"]))
AS_OF = f"{tx['date'].max():%d/%m/%Y}" if not tx.empty else "–"


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


def expiry_note(pid: int) -> str:
    if pid not in NEAREST.index:
        return ""
    left = int(NEAREST[pid])
    if left < 0:
        return f' · <b style="color:#9B1C1C">có lô quá hạn</b>'
    return f" · lô gần nhất còn {left} ngày"


def plot_layout(fig: go.Figure, title: str, height: int = 340, **kw) -> go.Figure:
    st.markdown(f"#### {title}")
    fig.update_layout(height=height, font=dict(family=FONT, color=INK), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", margin=dict(l=8, r=8, t=8, b=8),
                      legend=dict(orientation="h", y=-0.22, x=0, xanchor="left"), **kw)
    fig.update_xaxes(gridcolor="#E7ECE9", linecolor=LINE)
    fig.update_yaxes(gridcolor="#E7ECE9", linecolor=LINE)
    return fig


def page_stock() -> None:
    n_cats = stock["category"].nunique()
    page_head("Tồn kho", f"Tính đến {AS_OF} · {len(stock)} mặt hàng trong {n_cats} danh mục",
              (pg_tx, "Lập phiếu kho") if USER["can_write"] else None)

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
                sub = f"ROP {fmt_qty(r['rop'])} {r['unit']}"
            else:
                sub = f"đủ dùng {days_text(r)} · ROP {fmt_qty(r['rop'])} · nên đặt {fmt_qty(r['order_qty'])} {r['unit']}"
            items.append(
                f'<div class="sk-need"><span><b>{escape(r["name"])}</b>'
                f'<span class="sk-sub">Còn {fmt_qty(r["quantity"])} {escape(r["unit"])} · {sub}</span></span>'
                f'{pill(r["status"])}</div>')
        st.html('<section class="sk-card sk-pad" aria-label="Cần nhập hàng"><h3>Cần nhập hàng (tồn ≤ điểm đặt hàng ROP)</h3>'
                f'<div class="sk-needs">{"".join(items)}</div></section>')
        mine_below = needs[needs["id"].isin(MY_PIDS) & (needs["order_qty"] > 0)]
        if USER["can_write"] and not mine_below.empty:
            if st.button(f"Tạo phiếu nhập cho {len(mine_below)} mặt hàng dưới ROP", type="primary",
                         icon=":material/playlist_add:"):
                st.session_state["prefill_rop"] = True
                _reset_form("in")
                st.switch_page(pg_tx)

    with st.container(border=True, key="card1"):
        head, search = st.columns([3, 2], vertical_alignment="center")
        keyword = search.text_input("Tìm sản phẩm", placeholder="Tìm theo tên, ví dụ: gạo",
                                    label_visibility="collapsed", icon=":material/search:")
        cat_names = sorted(stock["category"].unique())
        cat_count = stock["category"].value_counts()
        options = ["Tất cả"] + cat_names
        sel = st.pills("Lọc theo danh mục", options, default="Tất cả", label_visibility="collapsed",
                       format_func=lambda c: f"{c} · {len(stock) if c == 'Tất cả' else cat_count[c]}")

        life = st.segmented_control(
            "Nhóm bảo quản", ["Tất cả", LONG_LIFE, SHORT_LIFE], default="Tất cả",
            help=f"Để lâu được: hạn dùng ≥ {LONG_LIFE_DAYS} ngày. Mau hỏng: hạn dùng ngắn hơn, phải bán nhanh.")
        view = stock if sel in (None, "Tất cả") else stock[stock["category"] == sel]
        if life not in (None, "Tất cả"):
            view = view[view["storage"] == life]
        if keyword.strip():
            view = view[view["name"].str.contains(keyword.strip(), case=False, regex=False)]
        head.markdown(f"#### Tất cả mặt hàng <span style='font-weight:400;color:{MUTED}'>({len(view)})</span>",
                      unsafe_allow_html=True)

        rows = []
        for _, r in view.iterrows():
            mn = float(r["rop"])
            scale = mn * 4 if mn > 0 else max(float(r["quantity"]), 1)
            bar = min(float(r["quantity"]) / scale, 1) * 100
            u = escape(r["unit"])
            rows.append(
                f'<tr><td><b>{escape(r["name"])}</b></td><td class="m">{escape(r["category"])}</td>'
                f'<td><span class="sk-pill neutral">{escape(r["storage"])}</span><br>'
                f'<span class="sk-sub">hạn {int(r["shelf_life_days"])} ngày{expiry_note(r["id"])}</span></td>'
                f'<td><div class="sk-meter"><div class="top"><b>{fmt_qty(r["quantity"])} {u}</b>'
                f'<span class="sk-sub">ROP {fmt_qty(mn)} {u}</span></div>'
                f'<div class="sk-bar"><i style="width:{bar:.1f}%;background:{STATUS_BAR[r["status"]]}"></i></div></div></td>'
                f'<td class="r">{fmt_qty(r["price"])} đ/{u}</td><td class="r"><b>{fmt_money(r["value"])}</b></td>'
                f'<td class="r">{days_text(r)}</td><td>{pill(r["status"])}</td></tr>')
        body = "".join(rows) if rows else ""
        empty = "" if rows else '<p class="sk-empty">Không có mặt hàng nào khớp. Thử xóa từ khóa hoặc chọn “Tất cả”.</p>'
        st.html(f"""
<div class="sk-wrap"><table class="sk-table">
<thead><tr><th>Sản phẩm</th><th>Danh mục</th><th>Bảo quản</th><th>Tồn kho so với điểm đặt hàng (ROP)</th>
<th class="r">Đơn giá</th><th class="r">Giá trị tồn</th><th class="r">Đủ dùng</th><th>Trạng thái</th></tr></thead>
<tbody>{body}</tbody></table>{empty}</div>
<p class="sk-note">Vạch đen trên thanh là điểm đặt hàng ROP = d × L + z × σ × √L (z = 1,65, mức phục vụ 95%). “Đủ dùng” = tồn kho chia cho lượng xuất
bình quân mỗi ngày trong {inventory.WINDOW_DAYS} ngày gần nhất.</p>""")

        export = view[["name", "category", "storage", "shelf_life_days", "unit", "quantity", "min_stock",
                       "price", "value", "out_window", "days_cover", "status"]]
        st.download_button("Tải bảng tồn kho (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                           file_name="ton_kho.csv", mime="text/csv", icon=":material/download:")


def _slip_lines(edited: pd.DataFrame, by_name: pd.DataFrame, with_price: bool) -> list[dict]:
    """Đổi bảng người dùng nhập thành các dòng phiếu (bỏ dòng trống)."""
    lines = []
    for _, r in edited.iterrows():
        name = r.get("Sản phẩm")
        qty = r.get("Số lượng")
        if not name or name not in by_name.index or pd.isna(qty) or float(qty) <= 0:
            continue
        p = by_name.loc[name]
        price = r.get("Đơn giá") if with_price else None
        price = float(p["price"]) if price is None or pd.isna(price) else float(price)
        lines.append({"product_id": int(p["id"]), "name": name, "unit": p["unit"], "quantity": float(qty),
                      "unit_price": price, "stock": float(p["quantity"]), "note": r.get("Ghi chú") or ""})
    return lines


def _open_time(key: str) -> str:
    """Giờ mở phiếu: ghi lại lần đầu form hiện ra, dùng để đo thời gian xử lý."""
    if key not in st.session_state:
        st.session_state[key] = db.now_str()
    return st.session_state[key]


def _reset_form(key: str) -> None:
    st.session_state.pop(f"open_{key}", None)
    st.session_state[f"ver_{key}"] = st.session_state.get(f"ver_{key}", 0) + 1


def next_batch(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now()
    return "Đợt 10h" if now.hour < 10 else "Đợt 15h" if now.hour < 15 else "Đợt 10h (sáng mai)"


def page_tx() -> None:
    page_head("Phiếu kho", "Phiếu nhập / hủy nhiều dòng ghi một lần; hàng xuất đi qua hàng chờ và được gom "
                           "theo đợt 10h, 15h. Mỗi phiếu tự ghi giờ mở và giờ ghi nhận để đo thời gian xử lý.")
    mine = stock[stock["id"].isin(MY_PIDS)].sort_values("name")
    if mine.empty:
        st.info("Chưa có sản phẩm nào bạn được giao phụ trách. Nhờ quản trị viên phân công danh mục."
                if not USER["is_admin"] else "Chưa có sản phẩm. Hãy thêm ở trang **Sản phẩm & danh mục**.")
        return
    by_name = mine.set_index("name")
    names = by_name.index.tolist()
    reqs = db.requests_df(conn)
    if not USER["is_admin"]:
        reqs = reqs[reqs["product_id"].isin(MY_PIDS)]
    waiting = reqs[reqs["status"] == "waiting"]
    n_pick = int((reqs["status"] == "picking").sum())
    labels = {"in": "Phiếu nhập / hủy", "req": f"Yêu cầu xuất ({len(waiting)} đang chờ)",
              "pick": f"Đợt xuất 10h / 15h ({n_pick} đang lấy)"}
    view = st.segmented_control("Mục", list(labels), format_func=labels.get, default="in", key="slip_view",
                                label_visibility="collapsed") or "in"
    tab_in = tab_req = tab_pick = None
    if view == "in":
        tab_in = st.container()
    elif view == "req":
        tab_req = st.container()
    else:
        tab_pick = st.container()

    # ---------------- Phiếu nhập / hủy nhiều dòng
    if tab_in is not None:
      with tab_in, st.container(border=True, key="card_slip_in"):
        a, b, c = st.columns([2, 1, 1], vertical_alignment="bottom")
        kind = a.segmented_control("Loại phiếu", [TX_IN, TX_DISPOSE], default=TX_IN, format_func=TX_LABEL.get,
                                   key="slip_kind") or TX_IN
        slip_day = b.date_input("Ngày", value=dt.date.today(), format="DD/MM/YYYY", key="slip_day")
        below = mine[(mine["status"] != IN_STOCK) & (mine["order_qty"] > 0)]
        if c.button(f"Hàng dưới ROP ({len(below)})", icon=":material/playlist_add:",
                    disabled=kind != TX_IN or below.empty, width="stretch"):
            st.session_state["prefill_rop"] = True
            _reset_form("in")
        if st.session_state.pop("prefill_rop", False) and not below.empty:
            st.session_state["slip_rows"] = pd.DataFrame({
                "Sản phẩm": below["name"], "Số lượng": below["order_qty"].astype(float),
                "Đơn giá": below["price"].astype(float), "Ghi chú": "Đặt theo ROP"}).reset_index(drop=True)
        rows = st.session_state.get("slip_rows")
        if rows is None:
            rows = pd.DataFrame({"Sản phẩm": [None], "Số lượng": [None], "Đơn giá": [None], "Ghi chú": [""]})
        started = _open_time("open_in")
        edited = st.data_editor(
            rows, num_rows="dynamic", width="stretch", hide_index=True, key=f"ed_in_{st.session_state.get('ver_in', 0)}",
            column_config={
                "Sản phẩm": st.column_config.SelectboxColumn(options=names, required=True, width="large"),
                "Số lượng": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%g"),
                "Đơn giá": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%g",
                                                         help="Để trống = đơn giá tham khảo của sản phẩm"),
                "Ghi chú": st.column_config.TextColumn()})
        lines = _slip_lines(edited, by_name, with_price=True)
        over = [l for l in lines if kind == TX_DISPOSE and l["quantity"] > l["stock"] + 1e-9]
        if lines:
            prev = "".join(
                f'<tr><td><b>{escape(l["name"])}</b></td><td class="r">{fmt_qty(l["quantity"])} {escape(l["unit"])}</td>'
                f'<td class="r">{fmt_money(l["unit_price"])}</td><td class="r">{fmt_money(l["quantity"] * l["unit_price"])}</td>'
                f'<td class="r">{fmt_qty(l["stock"])} → <b>{fmt_qty(l["stock"] + (l["quantity"] if kind == TX_IN else -l["quantity"]))}</b></td></tr>'
                for l in lines)
            html_table(["Sản phẩm", "Số lượng", "Đơn giá", "Thành tiền", "Tồn hiện tại → sau phiếu"], [prev],
                       right={1, 2, 3, 4}, cls="sk-compact")
        if over:
            st.error("Không đủ hàng để hủy: " + ", ".join(f'{l["name"]} (còn {fmt_qty(l["stock"])})' for l in over))
        total = sum(l["quantity"] * l["unit_price"] for l in lines)
        if st.button(f"Ghi nhận phiếu · {len(lines)} dòng · {fmt_money(total)}", type="primary", width="stretch",
                     disabled=not lines or bool(over), key="save_in"):
            try:
                oid = db.add_order(conn, kind, lines, slip_day, started_at=started, created_by=USER["username"])
                st.session_state.pop("slip_rows", None)
                _reset_form("in")
                notify(f"Đã ghi phiếu {oid}: {len(lines)} dòng, {fmt_money(total)}.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        st.caption(f"Phiếu mở lúc {started[11:16]}. Giờ ghi nhận lấy lúc bấm nút; KPI tính phút / dòng hàng.")

    # ---------------- Yêu cầu xuất
    if tab_req is not None:
      with tab_req, st.container(border=True, key="card_req"):
        st.markdown("#### Gửi yêu cầu xuất")
        st.caption("Yêu cầu vào hàng chờ, gom theo đợt 10h / 15h. Đánh dấu **Gấp** để kho xử lý ngay ngoài đợt.")
        all_names = stock.sort_values("name")["name"].tolist()
        all_by_name = stock.set_index("name")
        ed = st.data_editor(
            pd.DataFrame({"Sản phẩm": [None], "Số lượng": [None], "Ghi chú": [""]}), num_rows="dynamic",
            width="stretch", hide_index=True, key=f"ed_req_{st.session_state.get('ver_req', 0)}",
            column_config={"Sản phẩm": st.column_config.SelectboxColumn(options=all_names, required=True, width="large"),
                           "Số lượng": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%g"),
                           "Ghi chú": st.column_config.TextColumn()})
        rl = _slip_lines(ed, all_by_name, with_price=False)
        a, b = st.columns([1, 2], vertical_alignment="center")
        urgent = a.checkbox("Gấp", key="req_urgent", help="Xử lý ngay, không chờ đợt 10h / 15h")
        if b.button(f"Gửi yêu cầu · {len(rl)} dòng", type="primary", disabled=not rl, width="stretch"):
            try:
                n = db.add_requests(conn, rl, urgent, USER["username"])
                _reset_form("req")
                notify(f"Đã gửi {n} dòng yêu cầu xuất{' gấp' if urgent else ''} vào hàng chờ.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    if tab_req is not None:
      with tab_req, st.container(border=True, key="card_req_list"):
        st.markdown(f"#### Hàng chờ · {next_batch()} tiếp theo")
        if waiting.empty:
            st.caption("Không có yêu cầu nào đang chờ.")
        else:
            rows = [f'<tr><td>{tag("Gấp", "out") if r["urgent"] else tag("Thường", "neutral")}</td>'
                    f'<td><b>{escape(r["product"])}</b><br><span class="sk-sub">kệ {escape(r["shelf_location"] or "–")}'
                    f' · {escape(r["requested_by"] or "")} · {r["created_at"]:%d/%m %H:%M}</span></td>'
                    f'<td class="r">{fmt_qty(r["quantity"])} {escape(r["unit"])}</td></tr>' for _, r in waiting.iterrows()]
            html_table(["Loại", "Sản phẩm", "Số lượng"], rows, right={2}, cls="sk-compact")
            cid = st.selectbox("Hủy một yêu cầu", waiting["id"].tolist(), index=None, placeholder="Chọn yêu cầu…",
                               format_func=lambda i: f"#{i} · {waiting.set_index('id').at[i, 'product']}")
            if cid is not None and st.button("Hủy yêu cầu", icon=":material/close:"):
                db.cancel_request(conn, int(cid))
                notify(f"Đã hủy yêu cầu #{cid}.", ":material/close:")
                st.rerun()

    # ---------------- Đợt xuất & danh sách lấy hàng
    if tab_pick is not None:
      with tab_pick:
        urgent_w = waiting[waiting["urgent"] == 1]
        a, b = st.columns(2)
        with a, st.container(border=True, key="card_batch"):
            st.markdown(f"#### {next_batch()}")
            st.caption(f"{len(waiting)} dòng đang chờ ({len(urgent_w)} gấp). Đến giờ chốt thì tạo danh sách lấy hàng; "
                       "danh sách xếp theo vị trí kệ để đi một vòng là lấy đủ.")
            if st.button("Tạo danh sách lấy hàng", type="primary", disabled=waiting.empty, width="stretch",
                         icon=":material/checklist:"):
                pl = db.create_pick_list(conn, waiting["id"].tolist(), next_batch().split(" (")[0], USER["username"])
                notify(f"Đã tạo danh sách lấy hàng #{pl}.")
                st.rerun()
        with b, st.container(border=True, key="card_urgent"):
            st.markdown("#### Yêu cầu gấp")
            st.caption("Xử lý ngay, không chờ đợt.")
            if st.button(f"Xử lý gấp {len(urgent_w)} dòng", disabled=urgent_w.empty, width="stretch",
                         icon=":material/bolt:"):
                pl = db.create_pick_list(conn, urgent_w["id"].tolist(), "Gấp", USER["username"])
                notify(f"Đã tạo danh sách lấy hàng gấp #{pl}.")
                st.rerun()

        picking = reqs[reqs["status"] == "picking"]
        if picking.empty:
            st.info("Không có danh sách lấy hàng nào đang mở.")
        lists = db.pick_lists_df(conn).set_index("id")
        for pl_id, g in picking.groupby("pick_list_id"):
            pl = lists.loc[int(pl_id)]
            g = g.assign(_k=g["shelf_location"].fillna("ZZZ").replace("", "ZZZ")).sort_values(["_k", "product"])
            stock_now = stock.set_index("id")["quantity"]
            with st.container(border=True, key=f"card_pl_{int(pl_id)}"):
                st.markdown(f"#### Danh sách lấy hàng #{int(pl_id)} · {pl['kind']} · tạo lúc {pl['created_at'][11:16]}")
                rows = [f'<tr><td><b>{escape(r["shelf_location"] or "–")}</b></td><td><b>{escape(r["product"])}</b>'
                        f'<br><span class="sk-sub">{escape(r["note"] or "")}</span></td>'
                        f'<td class="r">{fmt_qty(r["quantity"])} {escape(r["unit"])}</td>'
                        f'<td class="r">{fmt_qty(stock_now.get(r["product_id"], 0))}</td>'
                        f'<td>{tag("Gấp", "out") if r["urgent"] else ""}</td></tr>' for _, r in g.iterrows()]
                html_table(["Kệ", "Sản phẩm", "Cần lấy", "Tồn hiện có", ""], rows, right={2, 3}, cls="sk-compact")
                c1, c2 = st.columns(2)
                c1.download_button("Tải để in (CSV)", g[["shelf_location", "product", "quantity", "unit", "note"]]
                                   .rename(columns={"shelf_location": "Kệ", "product": "Sản phẩm", "quantity": "Số lượng",
                                                    "unit": "Đơn vị", "note": "Ghi chú"})
                                   .to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"lay_hang_{int(pl_id)}.csv", mime="text/csv", icon=":material/print:",
                                   width="stretch", key=f"dl_pl_{int(pl_id)}")
                if c2.button("Xác nhận đã lấy xong", type="primary", width="stretch", key=f"done_pl_{int(pl_id)}"):
                    try:
                        res = db.complete_pick_list(conn, int(pl_id), USER["username"])
                        notify(f"Đã xuất phiếu {res['order_id']}: {res['lines']} dòng"
                               + (f", {res['short']} dòng thiếu hàng" if res["short"] else "") + ".")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    # ---------------- Phiếu gần đây (gộp theo mã phiếu)
    with st.container(border=True, key="card_orders"):
        h, lnk = st.columns([3, 2], vertical_alignment="center")
        h.markdown("#### Phiếu gần đây")
        lnk.page_link(pg_history, label="Xem toàn bộ lịch sử")
        t = tx[tx["product_id"].isin(MY_PIDS) & (tx["order_id"].fillna("") != "")]
        if t.empty:
            st.caption("Chưa có phiếu.")
        else:
            g = (t.assign(v=t["quantity"] * t["unit_price"], s=pd.to_datetime(t["started_at"]),
                          f=pd.to_datetime(t["finished_at"]))
                 .groupby("order_id").agg(date=("date", "max"), type=("type", "first"), n=("id", "count"),
                                          v=("v", "sum"), s=("s", "min"), f=("f", "max"), who=("created_by", "first"))
                 .sort_values(["date", "f"], ascending=False).head(10))
            rows = []
            for oid, r in g.iterrows():
                mins = (r["f"] - r["s"]).total_seconds() / 60 if pd.notna(r["f"]) and pd.notna(r["s"]) else None
                per = f"{mins:.0f} phút · {mins / r['n']:.1f} phút/dòng".replace(".", ",") if mins is not None else "–"
                rows.append(f'<tr><td class="nowrap">{r["date"]:%d/%m/%Y}</td>'
                            f'<td><b>{escape(oid)}</b><br><span class="sk-sub">{escape(TX_LABEL.get(r["type"], r["type"]))}'
                            f' · {escape(r["who"] or "")}</span></td><td class="r">{int(r["n"])}</td>'
                            f'<td class="r">{fmt_money(r["v"])}</td><td class="r">{per}</td></tr>')
            html_table(["Ngày", "Mã phiếu", "Số dòng", "Giá trị", "Thời gian xử lý"], rows, right={2, 3, 4},
                       cls="sk-compact")


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
                a, b, c, d = st.columns(4)
                price = a.number_input("Đơn giá (đ)", min_value=0.0, format="%g", step=1000.0)
                min_stock = b.number_input("Tồn tối thiểu", min_value=0.0, format="%g", step=1.0,
                                           help="Lượng dự trữ phải luôn giữ trong kho.")
                shelf = c.number_input("Hạn sử dụng (ngày)", min_value=1, value=365, step=1,
                                       help=f"≥ {LONG_LIFE_DAYS} ngày: để lâu được; ngắn hơn: mau hỏng.")
                opening = d.number_input("Tồn đầu kỳ", min_value=0.0, format="%g", step=1.0,
                                         help="Ghi thành một phiếu nhập.")
                a, b = st.columns(2)
                zone = a.selectbox("Khu bảo quản", ["", *ZONES], format_func=lambda z: z or "Tự chọn theo hạn dùng")
                cond = b.text_input("Điều kiện bảo quản", placeholder="Ví dụ: Thùng kín, kê cao khỏi sàn, chống mọt")
                a, b = st.columns(2)
                lead = a.number_input("Thời gian chờ giao (ngày)", min_value=0, max_value=90, value=2, step=1,
                                      help="Số ngày từ lúc đặt đến lúc nhà cung cấp giao, dùng tính ROP.")
                shelf_loc = b.text_input("Vị trí kệ", placeholder="Ví dụ: A-01 (dãy A gần cửa xuất)")
                note = st.text_input("Ghi chú")
                if st.form_submit_button("Thêm sản phẩm", type="primary", icon=":material/add:"):
                    try:
                        db.add_product(conn, name, cid, unit, price, min_stock, note, opening,
                                       shelf_life_days=int(shelf), storage_zone=zone, storage_note=cond,
                                       lead_time_days=int(lead), shelf_location=shelf_loc)
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
                    a, b, c = st.columns(3)
                    price = a.number_input("Đơn giá (đ)", min_value=0.0, format="%g", step=1000.0,
                                           value=float(e["price"]))
                    min_stock = b.number_input("Tồn tối thiểu", min_value=0.0, format="%g", step=1.0,
                                               value=float(e["min_stock"]))
                    shelf = c.number_input("Hạn sử dụng (ngày)", min_value=1, step=1,
                                           value=int(e["shelf_life_days"]),
                                           help=f"≥ {LONG_LIFE_DAYS} ngày: để lâu được; ngắn hơn: mau hỏng.")
                    zopts = ["", *ZONES]
                    cur_zone = e["storage_zone"] if e["storage_zone"] in zopts else ""
                    a, b = st.columns(2)
                    zone = a.selectbox("Khu bảo quản", zopts, index=zopts.index(cur_zone),
                                       format_func=lambda z: z or "Tự chọn theo hạn dùng")
                    cond = b.text_input("Điều kiện bảo quản", value=e["storage_note"] or "")
                    a, b = st.columns(2)
                    lead = a.number_input("Thời gian chờ giao (ngày)", min_value=0, max_value=90, step=1,
                                          value=int(e["lead_time_days"]))
                    shelf_loc = b.text_input("Vị trí kệ", value=e["shelf_location"] or "")
                    note = st.text_input("Ghi chú", value=e["note"] or "")
                    st.caption("Số lượng tồn kho không sửa ở đây: hãy ghi phiếu nhập / xuất để sổ luôn khớp.")
                    if st.form_submit_button("Lưu thay đổi", type="primary"):
                        try:
                            db.update_product(conn, int(eid), name, cid, unit, price, min_stock, note,
                                              shelf_life_days=int(shelf), storage_zone=zone,
                                              storage_note=cond, lead_time_days=int(lead),
                                              shelf_location=shelf_loc)
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
            f'{c["products"]} sản phẩm · quản lý: {escape(c["manager"] or "chưa giao")}</span></div></li>'
            for _, c in cats.iterrows())
        st.html(f'<ul class="sk-list">{items}</ul>')
        if not cats.empty:
            users = auth.users_df(conn)
            uopts = [None] + users["id"].tolist()
            uname = dict(zip(users["id"], [f or u for f, u in zip(users["full_name"], users["username"])]))
            with st.expander("Người quản lý phụ trách", icon=":material/supervisor_account:"):
                st.caption("Mỗi danh mục giao cho một người. KPI của người đó tính từ các danh mục được giao.")
                with st.form("assign_mgr", border=False):
                    picks = {}
                    for _, c in cats.iterrows():
                        cur = None if pd.isna(c["manager_id"]) else int(c["manager_id"])
                        picks[int(c["id"])] = st.selectbox(
                            c["name"], uopts, index=uopts.index(cur) if cur in uopts else 0,
                            format_func=lambda u: "Chưa giao" if u is None else uname[u], key=f"mgr_{c['id']}")
                    if st.form_submit_button("Lưu phân công", type="primary"):
                        for cid_, uid_ in picks.items():
                            db.set_category_manager(conn, cid_, uid_)
                        notify("Đã lưu phân công người quản lý.")
                        st.rerun()
        if not cats.empty:
            did = st.selectbox("Xóa danh mục", cats["id"].tolist(), format_func=cat_label, key="del_cat")
            st.caption("Sản phẩm trong danh mục bị xóa sẽ chuyển sang “Chưa phân loại”.")
            if st.button("Xóa danh mục", icon=":material/delete:"):
                db.delete_category(conn, int(did))
                notify(f"Đã xóa danh mục “{cat_label(did)}”.", ":material/delete:")
                st.rerun()


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

    with a, st.container(border=True, key="card9"):
        per = st.segmented_control("Kỳ", ["Theo tháng", "Theo quý"], default="Theo tháng",
                                   label_visibility="collapsed") or "Theo tháng"
        quarterly = per == "Theo quý"
        flow = inventory.monthly_flow(tx, "Q" if quarterly else "M")
        labels = ([f"Q{m[-1]}/{m[:4]}" for m in flow["month"]] if quarterly
                  else [f"T{int(m[5:])}/{m[:4]}" for m in flow["month"]])
        fig = go.Figure()
        fig.add_bar(x=labels, y=flow["Nhập kho"], name="Nhập kho", marker_color=ACCENT)
        fig.add_bar(x=labels, y=flow["Xuất kho"], name="Xuất kho", marker_color=OUT_COLOR)
        fig.add_bar(x=labels, y=flow["Hủy hàng"], name="Hủy hàng", marker_color="#7F1D13")
        st.plotly_chart(plot_layout(fig, f"Giá trị nhập / xuất / hủy {per.lower()}", barmode="group",
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

    with a, st.container(border=True, key="card_storage"):
        g = stock.groupby("storage").agg(value=("value", "sum"), n=("id", "count")).reindex([LONG_LIFE, SHORT_LIFE]).fillna(0)
        fig = go.Figure(go.Pie(labels=list(g.index), values=g["value"], hole=0.55,
                               marker=dict(colors=[ACCENT, OUT_COLOR]),
                               text=[f"{int(n)} mặt hàng" for n in g["n"]], textinfo="label+percent"))
        st.plotly_chart(plot_layout(fig, "Giá trị tồn theo nhóm bảo quản", showlegend=False), width="stretch")
    with b, st.container(border=True, key="card_disposal"):
        d = tx[tx["type"] == TX_DISPOSE]
        d = d.assign(v=d["quantity"] * d["unit_price"],
                     q="Q" + d["date"].dt.quarter.astype(str) + "/" + d["date"].dt.year.astype(str))
        pv = d.pivot_table(index="q", columns="product", values="v", aggfunc="sum", fill_value=0)
        fig = go.Figure()
        for i, col in enumerate(pv.columns):
            fig.add_bar(x=list(pv.index), y=pv[col], name=col,
                        marker_color=["#7F1D13", "#B45309", "#1D4ED8", "#2F7D53", "#6B21A8"][i % 5])
        st.plotly_chart(plot_layout(fig, "Giá trị hàng hủy (hết hạn) theo quý", barmode="stack",
                                    yaxis_title="đ"), width="stretch")


def page_history() -> None:
    if tx.empty:
        page_head("Lịch sử giao dịch", "Chưa có giao dịch.")
        return
    head_slot = st.empty()
    with st.container(border=True, key="card11"):
        a, b, c, d = st.columns([2, 1, 1, 2])
        q = a.text_input("Sản phẩm", placeholder="Tìm theo tên")
        types = b.selectbox("Loại", ["", TX_IN, TX_OUT, TX_DISPOSE, TX_ADJ_PLUS, TX_ADJ_MINUS],
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
            "Người lập": h["created_by"].fillna(""),
            "Mã phiếu": h["order_id"].fillna(""),
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


def page_account() -> None:
    page_head("Tài khoản", f"{USER['full_name']} · {USER['username']} · {auth.ROLE_LABEL[USER['role']]}")
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
            role = st.selectbox("Vai trò", auth.ROLES, index=1, format_func=auth.ROLE_LABEL.get,
                                help="Quản lý kho: ghi phiếu và kiểm kê cho danh mục được giao, được chấm KPI. "
                                     "Chỉ xem: xem tồn kho, báo cáo, lịch sử.")
            if st.form_submit_button("Thêm tài khoản", type="primary", icon=":material/person_add:"):
                try:
                    auth.create_user(conn, username, pw, name, role=role)
                    notify(f"Đã thêm tài khoản “{auth.normalize_username(username)}”.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with st.container(border=True, key="card_users"):
        st.markdown("#### Danh sách tài khoản")
        users = auth.users_df(conn)
        st.dataframe(pd.DataFrame({
            "Tài khoản": users["username"], "Họ tên": users["full_name"],
            "Vai trò": users["role"].map(auth.ROLE_LABEL),
            "Ngày tạo": users["created_at"],
        }), hide_index=True, width="stretch")

        others = users[users["id"] != USER["id"]]
        if others.empty:
            return
        by_id = others.set_index("id")
        a, b = st.columns(2, vertical_alignment="bottom")
        uid = a.selectbox("Chọn tài khoản", by_id.index.tolist(),
                          format_func=lambda i: f"{by_id.at[i, 'username']} — {by_id.at[i, 'full_name'] or ''}")
        with b.popover("Đổi vai trò", icon=":material/badge:"):
            cur_role = by_id.at[uid, "role"]
            new_role = st.selectbox("Vai trò mới", auth.ROLES, index=auth.ROLES.index(cur_role),
                                    format_func=auth.ROLE_LABEL.get, key=f"role_{uid}")
            if st.button("Lưu vai trò", type="primary", key=f"save_role_{uid}"):
                try:
                    auth.set_role(conn, int(uid), new_role, USER["id"])
                    notify(f"Đã đổi vai trò “{by_id.at[uid, 'username']}” thành {auth.ROLE_LABEL[new_role]}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
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


KPI_CLS = {kpi.GOOD: "ok", kpi.WARN: "low", kpi.BAD: "out", kpi.NA: "neutral"}
RISK_CLS = {risk.HIGH: "out", risk.MEDIUM: "low", risk.LOW: "neutral"}
PRIORITY_CLS = {"Cao": "out", "Trung bình": "low", "Theo dõi": "neutral"}
GRADE_COLOR = {"A": "#2F7D53", "B": "#1D4ED8", "C": "#B45309", "D": "#7F1D13"}


@st.cache_data(show_spinner="Đang tính KPI theo quý...")
def cached_quarterly(products_: pd.DataFrame, tx_: pd.DataFrame,
                     counts_: pd.DataFrame | None = None) -> pd.DataFrame:
    return kpi.quarterly_table(products_, tx_, counts_)


@st.cache_data(show_spinner=False)
def cached_daily(products_: pd.DataFrame, tx_: pd.DataFrame) -> pd.DataFrame:
    return inventory.daily_stock(products_, tx_)


def tag(text: str, cls: str) -> str:
    return f'<span class="sk-pill {cls}">{escape(text)}</span>'


def stat_cards(items: list[tuple]) -> None:
    html = "".join(
        f'<div class="sk-stat {cls}"><span class="l">{escape(label)}</span>'
        f'<span class="v">{value}</span>{f"<span class=sk-sub>{note}</span>" if note else ""}</div>'
        for label, value, cls, note in items)
    st.html(f'<section class="sk-stats">{html}</section>')


def html_table(head: list[str], rows: list[str], right: set[int] = frozenset(), empty: str = "Không có dữ liệu.",
               cls: str = "") -> None:
    th = "".join(f'<th class="{"r" if i in right else ""}">{h}</th>' for i, h in enumerate(head))
    body = "".join(rows)
    tail = "" if rows else f'<p class="sk-empty">{escape(empty)}</p>'
    st.html(f'<div class="sk-wrap"><table class="sk-table {cls}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table>{tail}</div>')


def page_daily() -> None:
    if tx.empty:
        page_head("Báo cáo cuối ngày", "Chưa có giao dịch.")
        return
    last = tx["date"].max().date()
    top_l, top_r = st.columns([2, 1], vertical_alignment="bottom")
    day = top_r.date_input("Ngày báo cáo", value=last, min_value=tx["date"].min().date(),
                           max_value=max(last, dt.date.today()), format="DD/MM/YYYY")
    with top_l:
        page_head("Báo cáo cuối ngày", f"Nhập – xuất – hủy – tồn cuối ngày {day:%d/%m/%Y}, "
                                      "kèm hàng cận hạn và hàng dưới mức dự trữ.")
    rep = inventory.daily_report(products, tx, pd.Timestamp(day))
    rep["category"] = rep["category"].fillna(UNCATEGORIZED)
    in_val = float((rep["in"] * rep["price"]).sum())
    disp_val = float((rep["dispose"] * rep["price"]).sum())
    near = rep[rep["near_qty"] > 0]
    under = rep[rep["status"] != IN_STOCK]
    stat_cards([
        ("Giá trị xuất bán trong ngày", fmt_money(rep["sales_value"].sum()), "", None),
        ("Giá trị nhập trong ngày", fmt_money(in_val), "", None),
        ("Hàng hủy trong ngày", fmt_money(disp_val), "out" if disp_val > 0 else "", None),
        ("Tồn cuối ngày", fmt_money(rep["value"].sum()), "", None),
        ("Dưới mức dự trữ", f"{len(under)} <small>mặt hàng</small>", "low" if len(under) else "", None),
        ("Có lô cận hạn", f"{len(near)} <small>mặt hàng</small>", "low" if len(near) else "", None),
    ])

    with st.container(border=True, key="card_daily"):
        only = st.segmented_control("Hiển thị", ["Tất cả", "Có phát sinh", "Cần chú ý"], default="Tất cả",
                                    label_visibility="collapsed") or "Tất cả"
        view = rep
        if only == "Có phát sinh":
            view = rep[(rep["in"] + rep["out"] + rep["dispose"] + rep["adjust"].abs()) > 0]
        elif only == "Cần chú ý":
            view = rep[(rep["status"] != IN_STOCK) | (rep["near_qty"] > 0)]
        rows = []
        for _, r in view.sort_values(["category", "name"]).iterrows():
            u = escape(r["unit"])
            left = "–" if pd.isna(r["days_left"]) else f"{int(r['days_left'])} ngày"
            near_txt = f'<br><span class="sk-sub">cận hạn {fmt_qty(r["near_qty"])} {u}</span>' if r["near_qty"] > 0 else ""
            rows.append(
                f'<tr><td><b>{escape(r["name"])}</b><br><span class="sk-sub">{escape(r["category"])}</span></td>'
                f'<td>{tag(storage_class(r["shelf_life_days"]), "neutral")}</td>'
                f'<td class="r">{fmt_qty(r["opening"])} {u}</td><td class="r">{fmt_qty(r["in"])}</td>'
                f'<td class="r">{fmt_qty(r["out"])}</td><td class="r">{fmt_qty(r["dispose"])}</td>'
                f'<td class="r">{("+" if r["adjust"] > 0 else "") + fmt_qty(r["adjust"]) if r["adjust"] else "0"}</td>'
                f'<td class="r"><b>{fmt_qty(r["closing"])} {u}</b></td>'
                f'<td class="r">{left}{near_txt}</td><td>{pill(r["status"])}</td></tr>')
        html_table(["Sản phẩm", "Bảo quản", "Tồn đầu ngày", "Nhập", "Xuất", "Hủy", "Kiểm kê ±",
                    "Tồn cuối ngày", "Lô gần hết hạn", "Trạng thái"], rows, right={2, 3, 4, 5, 6, 7, 8},
                   empty="Không có mặt hàng nào khớp.")
        export = view[["name", "category", "unit", "shelf_life_days", "opening", "in", "out", "dispose",
                       "adjust", "closing", "value", "near_qty", "days_left", "status"]]
        st.download_button("Tải báo cáo ngày (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"bao_cao_ngay_{day:%Y%m%d}.csv", mime="text/csv",
                           icon=":material/download:")


def page_kpi() -> None:
    q = cached_quarterly(products, tx, STOCKTAKES)
    if q.empty:
        page_head("Đánh giá KPI", "Chưa có dữ liệu.")
        return
    periods = list(q.index)
    top_l, top_r = st.columns([2, 1], vertical_alignment="bottom")
    sel = top_r.selectbox("Quý đánh giá", periods, index=len(periods) - 1)
    with top_l:
        page_head("KPI toàn kho theo quý", f"Đối tượng: {kpi.OBJECT} (tất cả danh mục). "
                  "KPI từng người quản lý xem ở trang KPI người quản lý kho.")
    i = periods.index(sel)
    row, prev = q.loc[sel], (q.iloc[i - 1] if i > 0 else None)
    letter, text = kpi.grade(row["score"])
    statuses = {k: kpi.evaluate(k, row[k]) for k in kpi.KPI_DEFS}
    n = {s: sum(v == s for v in statuses.values()) for s in (kpi.GOOD, kpi.WARN, kpi.BAD)}
    if prev is not None:
        d = row["score"] - prev["score"]
        trend = (f"{'Tăng' if d > 0 else 'Giảm' if d < 0 else 'Giữ nguyên'} "
                 f"{abs(d):.0f} điểm so với {periods[i - 1]}")
    else:
        trend = "Quý đầu tiên có dữ liệu"
    stat_cards([
        ("Điểm tổng hợp", f"{row['score']:.0f} <small>/ 100</small>", "", trend),
        ("Xếp loại người phụ trách kho", f'<span style="color:{GRADE_COLOR[letter]}">{letter}</span> '
                                        f"<small>{text}</small>", "", "A ≥ 85 · B ≥ 70 · C ≥ 50 · D < 50"),
        ("Chỉ số đạt", f"{n[kpi.GOOD]} <small>/ {len(statuses)}</small>", "", None),
        ("Cảnh báo / chưa đạt", f"{n[kpi.WARN]} <small>cảnh báo</small> · {n[kpi.BAD]} <small>chưa đạt</small>",
         "out" if n[kpi.BAD] else "low" if n[kpi.WARN] else "", None),
    ])

    with st.container(border=True, key="card_kpi_table"):
        st.markdown(f"#### Kết quả {sel}")
        rows = []
        for group in kpi.CRITERIA:
            keys = [k for k, d in kpi.KPI_DEFS.items() if d["group"] == group]
            for j, k in enumerate(keys):
                d = kpi.KPI_DEFS[k]
                change = "–"
                if prev is not None:
                    delta = row[k] - prev[k]
                    better = delta > 1e-9 if d["higher"] else delta < -1e-9
                    worse = delta < -1e-9 if d["higher"] else delta > 1e-9
                    sign = "+" if delta > 0 else ""
                    val = (f"{sign}{delta:.1f}" if d["fmt"] != "int" else f"{sign}{delta:.0f}").replace(".", ",")
                    change = (tag(f"▲ {val} cải thiện", "ok") if better else
                              tag(f"▼ {val} xấu đi", "out") if worse else tag("không đổi", "neutral"))
                crit = f'<td rowspan="{len(keys)}"><b>{escape(group)}</b></td>' if j == 0 else ""
                rows.append(
                    f'<tr>{crit}<td>{escape(d["label"])}<br><span class="sk-sub">trọng số {d["weight"]}%</span></td>'
                    f'<td class="r"><b>{kpi.fmt_value(k, row[k])}</b></td>'
                    f'<td><span class="sk-sub">{escape(kpi.standard_text(k))}</span></td>'
                    f'<td>{tag(statuses[k], KPI_CLS[statuses[k]])}</td><td>{change}</td></tr>')
        html_table(["Tiêu chí", "Chỉ số (Index)", "Kết quả", "Tiêu chuẩn", "Đánh giá", "So với quý trước"],
                   rows, right={2})
        st.caption("Điểm tổng hợp = Σ trọng số × hệ số (Đạt 100% · Cảnh báo 60% · Chưa đạt 20%).")

    with st.expander("Khung đánh giá: đối tượng, tiêu chí, công thức và dữ liệu", icon=":material/rule:"):
        st.markdown(f"**1. Đối tượng:** {kpi.OBJECT}.  \n**2. Tiêu chí → Chỉ số → Tiêu chuẩn** như bảng dưới.  \n"
                    "**3. Dữ liệu:** lịch sử phiếu nhập / xuất / hủy hàng, danh mục sản phẩm "
                    "(đơn giá, mức dự trữ tối thiểu, hạn sử dụng).")
        rows = [f'<tr><td>{escape(d["group"])}</td><td><b>{escape(d["label"])}</b></td>'
                f'<td>{escape(d["formula"])}</td><td>{escape(kpi.standard_text(k))}</td>'
                f'<td class="r">{d["weight"]}%</td><td><span class="sk-sub">{escape(d["data"])}</span></td></tr>'
                for k, d in kpi.KPI_DEFS.items()]
        html_table(["Tiêu chí", "Chỉ số", "Công thức", "Tiêu chuẩn", "Trọng số", "Nguồn dữ liệu"], rows, right={4})

    a, b = st.columns(2)
    with a, st.container(border=True, key="card_kpi_score"):
        colors = [GRADE_COLOR[g] for g in q["grade"]]
        fig = go.Figure(go.Bar(x=list(q.index), y=q["score"], marker_color=colors,
                               text=[f"{s:.0f} · {g}" for s, g in zip(q["score"], q["grade"])],
                               textposition="inside", insidetextanchor="end", textfont=dict(color="#FFFFFF")))
        fig.add_hline(y=85, line_dash="dash", line_color="#2F7D53", annotation_text="Loại A (85)",
                      annotation_position="top left")
        fig.add_hline(y=70, line_dash="dot", line_color="#B45309", annotation_text="Loại B (70)",
                      annotation_position="bottom left")
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(plot_layout(fig, "Điểm tổng hợp & xếp loại qua các quý", yaxis_title="điểm"),
                        width="stretch")
    with b, st.container(border=True, key="card_kpi_trend"):
        key = st.selectbox("Chỉ số", list(kpi.KPI_DEFS), format_func=lambda k: kpi.KPI_DEFS[k]["label"],
                           key="kpi_trend_key")
        d = kpi.KPI_DEFS[key]
        fig = go.Figure(go.Bar(
            x=list(q.index), y=q[key],
            marker_color=[STATUS_BAR[{kpi.GOOD: IN_STOCK, kpi.WARN: LOW_STOCK, kpi.BAD: OUT_OF_STOCK}[kpi.evaluate(key, v)]]
                          for v in q[key]],
            text=[kpi.fmt_value(key, v) for v in q[key]], textposition="inside", insidetextanchor="end",
            textfont=dict(color="#FFFFFF")))
        fig.add_hline(y=d["target"], line_dash="dash", line_color="#2F7D53",
                      annotation_text=f"Mục tiêu {kpi.fmt_value(key, d['target'])}",
                      annotation_position="top left")
        fig.add_hline(y=d["warn"], line_dash="dot", line_color="#B45309",
                      annotation_text=f"Cảnh báo {kpi.fmt_value(key, d['warn'])}",
                      annotation_position="bottom left")
        st.plotly_chart(plot_layout(fig, f"Xu hướng: {d['label']}", yaxis_title=d["unit"]), width="stretch")

    with st.container(border=True, key="card_kpi_plan"):
        st.markdown(f"#### Phương án cải tiến cho {sel}")
        plans = kpi.improvement_plan(products, tx, row, prev, cached_daily(products, tx), STOCKTAKES)
        if not plans:
            st.success("Tất cả chỉ số đều đạt và không xấu đi so với quý trước. Duy trì quy trình hiện tại.")
        rows = []
        for p in plans:
            items = ", ".join(p["items"]) if p["items"] else "–"
            rows.append(
                f'<tr><td>{tag(p["priority"], PRIORITY_CLS[p["priority"]])}</td>'
                f'<td><b>{escape(p["label"])}</b><br><span class="sk-sub">{escape(p["group"])} · '
                f'kết quả {escape(p["value"])} ({escape(p["status"])})</span></td>'
                f'<td>{escape(items)}</td><td>{escape(p["action"])}</td></tr>')
        if rows:
            html_table(["Ưu tiên", "Chỉ số cần cải thiện", "Mặt hàng ảnh hưởng nhiều nhất", "Biện pháp"], rows)

    export = q.drop(columns=["start", "end"]).rename(columns={k: d["label"] for k, d in kpi.KPI_DEFS.items()})
    st.download_button("Tải báo cáo KPI theo quý (CSV)", export.to_csv().encode("utf-8-sig"),
                       file_name="kpi_theo_quy.csv", mime="text/csv", icon=":material/download:")


def page_risk() -> None:
    if tx.empty:
        page_head("Quản lý rủi ro", "Chưa có giao dịch.")
        return
    last = tx["date"].max().date()
    top_l, top_r = st.columns([2, 1], vertical_alignment="bottom")
    day = top_r.date_input("Đánh giá tại ngày", value=last, min_value=tx["date"].min().date(),
                           max_value=max(last, dt.date.today()), format="DD/MM/YYYY", key="risk_day")
    with top_l:
        page_head("Quản lý rủi ro tồn kho", "Nhận diện → đánh giá (khả năng × ảnh hưởng) → biện pháp xử lý.")
    reg = risk.register(products, tx, pd.Timestamp(day))
    n = {lv: int((reg["level"] == lv).sum()) if not reg.empty else 0 for lv in risk.LEVELS}
    stat_cards([
        ("Rủi ro cao", f"{n[risk.HIGH]} <small>mục</small>", "out" if n[risk.HIGH] else "", "xử lý ngay trong ngày"),
        ("Rủi ro trung bình", f"{n[risk.MEDIUM]} <small>mục</small>", "low" if n[risk.MEDIUM] else "", "xử lý trong tuần"),
        ("Rủi ro thấp", f"{n[risk.LOW]} <small>mục</small>", "", "theo dõi"),
        ("Giá trị hàng chịu rủi ro", fmt_money(reg["value"].sum() if not reg.empty else 0), "", "cận hạn, quá hạn, tồn đọng, dưới dự trữ"),
    ])
    if reg.empty:
        st.success("Không phát hiện rủi ro nào tại ngày này.")
        return

    a, b = st.columns(2)
    with a, st.container(border=True, key="card_risk_matrix"):
        grid = [[0] * 5 for _ in range(5)]
        for _, r in reg.iterrows():
            grid[int(r["impact"]) - 1][int(r["likelihood"]) - 1] += 1
        score = [[(li + 1) * (im + 1) for li in range(5)] for im in range(5)]
        z = [[0 if v < 8 else 1 if v < 15 else 2 for v in r_] for r_ in score]
        text = [[str(grid[im][li]) if grid[im][li] else "" for li in range(5)] for im in range(5)]
        fig = go.Figure(go.Heatmap(
            z=z, x=[1, 2, 3, 4, 5], y=[1, 2, 3, 4, 5], text=text, texttemplate="%{text}",
            customdata=score, textfont=dict(size=18, color="#FFFFFF"), showscale=False, zmin=0, zmax=2,
            xgap=2, ygap=2,
            colorscale=[[0, "#7FA393"], [0.33, "#7FA393"], [0.34, "#B45309"], [0.66, "#B45309"],
                        [0.67, "#7F1D13"], [1, "#7F1D13"]],
            hovertemplate="Khả năng %{x} × Ảnh hưởng %{y} = %{customdata}<br>Số rủi ro: %{text}<extra></extra>"))
        fig.update_xaxes(dtick=1)
        fig.update_yaxes(dtick=1)
        st.plotly_chart(plot_layout(fig, "Ma trận rủi ro", xaxis_title="Khả năng xảy ra (1–5)",
                                    yaxis_title="Mức ảnh hưởng (1–5)"), width="stretch")
        st.caption("Xanh: thấp (< 8) · Cam: trung bình (8–14) · Đỏ: cao (≥ 15). Số trong ô là số rủi ro.")
    with b, st.container(border=True, key="card_risk_types"):
        by = reg.groupby(["risk", "level"]).size().unstack(fill_value=0)
        fig = go.Figure()
        for lv, color in ((risk.HIGH, "#7F1D13"), (risk.MEDIUM, "#B45309"), (risk.LOW, "#9DB8AA")):
            if lv in by.columns:
                fig.add_bar(y=by.index, x=by[lv], name=lv, orientation="h", marker_color=color)
        st.plotly_chart(plot_layout(fig, "Rủi ro theo loại", barmode="stack", xaxis_title="số mục"),
                        width="stretch")

    with st.container(border=True, key="card_risk_list"):
        st.markdown("#### Danh sách rủi ro & biện pháp")
        rows = [f'<tr><td>{tag(r["level"], RISK_CLS[r["level"]])}<br><span class="sk-sub">điểm {r["score"]}</span></td>'
                f'<td><b>{escape(r["product"])}</b><br><span class="sk-sub">{escape(r["category"])}</span></td>'
                f'<td><b>{escape(r["risk"])}</b><br><span class="sk-sub">{escape(r["detail"])}</span></td>'
                f'<td class="r">{r["likelihood"]} × {r["impact"]}</td><td>{escape(r["action"])}</td></tr>'
                for _, r in reg.iterrows()]
        html_table(["Mức", "Sản phẩm", "Rủi ro", "Khả năng × Ảnh hưởng", "Biện pháp"], rows, right={3})
        st.download_button("Tải danh sách rủi ro (CSV)",
                           reg.drop(columns=["product_id", "kind"]).to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"rui_ro_{day:%Y%m%d}.csv", mime="text/csv", icon=":material/download:")


LOT_STATE = {
    "safe": ("ok", "An toàn", "Xuất theo nhập trước – xuất trước."),
    "first": ("low", "Ưu tiên xuất trước", "Bán lô cũ trước; không nhập thêm đến khi lô cũ gần hết."),
    "near": ("out", "Cận hạn", "Đẩy bán / giảm giá ngay; kiểm tra chất lượng."),
    "exp": ("exp", "Quá hạn", "Tách riêng, lập phiếu hủy hàng."),
}
STATE_ORDER = ["safe", "first", "near", "exp"]


def lot_state(row, life: int) -> str:
    if row["expired"]:
        return "exp"
    if row["near"]:
        return "near"
    return "first" if row["days_left"] / life <= 0.5 else "safe"


def approx_life(days: int) -> str:
    if days < 60:
        return ""
    if days < 365:
        return f"≈ {days / 30:.0f} tháng · "
    return f"≈ {days / 365:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " năm · "


def page_storage() -> None:
    if products.empty:
        page_head("Thời hạn bảo quản trong kho", "Chưa có sản phẩm.")
        return
    as_of = tx["date"].max() if not tx.empty else pd.Timestamp(dt.date.today())
    lots = LOTS_NOW.copy()
    life_of = dict(zip(products["id"], products["shelf_life_days"].astype(int)))
    if not lots.empty:
        lots["stored"] = (as_of - lots["in_date"]).dt.days
        lots["life"] = lots["product_id"].map(life_of)
        lots["state"] = [lot_state(r, int(r["life"])) for _, r in lots.iterrows()]
    else:
        lots = lots.assign(stored=[], life=[], state=[])

    prods = stock.copy()
    prods["zone"] = [zone_of(z, s) for z, s in zip(prods["storage_zone"], prods["shelf_life_days"])]
    prods["nearest"] = prods["id"].map(lots.groupby("product_id")["days_left"].min() if not lots.empty
                                       else pd.Series(dtype=float))
    prods["worst"] = prods["id"].map(
        lots.groupby("product_id")["state"].agg(lambda s: max(s, key=STATE_ORDER.index))
        if not lots.empty else pd.Series(dtype=object))

    top_l, top_r = st.columns([3, 2], vertical_alignment="bottom")
    with top_l:
        page_head("Thời hạn bảo quản trong kho",
                  f"Tính đến {as_of:%d/%m/%Y}. Mỗi mặt hàng: còn bao nhiêu ngày nữa hết hạn, ngày hết hạn, "
                  "đã lưu kho bao lâu và điều kiện cần giữ. Hàng sắp hết hạn xếp lên đầu.")
    zones_here = [z for z in ZONES if z in set(prods["zone"])]
    flt = top_r.segmented_control("Lọc", ["Tất cả"] + zones_here + ["Sắp hết hạn"], default="Tất cả",
                                  label_visibility="collapsed") or "Tất cả"

    n_state = lots["state"].value_counts() if not lots.empty else pd.Series(dtype=int)
    cold = lots[lots["product_id"].map(dict(zip(prods["id"], prods["zone"]))) == ZONE_COLD] if not lots.empty else lots
    soonest = lots.sort_values("days_left").iloc[0] if not lots.empty else None
    near_exp = int(n_state.get("near", 0)) + int(n_state.get("exp", 0))
    stat_cards([
        ("Lô hàng đang lưu kho", f"{len(lots)}", "", f"{lots['product_id'].nunique() if not lots.empty else 0} mặt hàng"),
        (f"Lô trong {ZONE_COLD}", f"{len(cold)}", "",
         f"lưu bình quân {cold['stored'].mean():.0f} ngày" if len(cold) else "không có"),
        ("Ưu tiên xuất trước", f"{int(n_state.get('first', 0))}", "low" if n_state.get("first", 0) else "",
         "còn ≤ 50% hạn dùng"),
        ("Lô sắp hết hạn nhất",
         f"{int(soonest['days_left'])} <small>ngày</small>" if soonest is not None else "–", "",
         (f"{escape(names_by_id.get(soonest['product_id'], ''))}, hết hạn {soonest['expiry']:%d/%m}"
          if soonest is not None else None)),
        ("Cận hạn / quá hạn", f"{int(n_state.get('near', 0))} / {int(n_state.get('exp', 0))}",
         "out" if near_exp else "", "còn ≤ 20% hạn / đã quá hạn"),
    ])
    st.html('<div class="sk-legend"><span><i class="safe"></i>An toàn: còn &gt; 50% hạn dùng</span>'
            '<span><i class="first"></i>Ưu tiên xuất trước: còn 20–50%</span>'
            '<span><i class="near"></i>Cận hạn: còn ≤ 20%</span><span><i class="exp"></i>Quá hạn</span></div>')

    view = prods
    if flt == "Sắp hết hạn":
        view = prods[prods["worst"].isin(["first", "near", "exp"])]
    elif flt != "Tất cả":
        view = prods[prods["zone"] == flt]
    if view.empty:
        st.success("Không có mặt hàng nào sắp hết hạn.")
        return

    for zone in ZONES:
        zv = view[view["zone"] == zone].assign(_k=lambda d: d["nearest"].fillna(10 ** 6)).sort_values(["_k", "name"])
        if zv.empty:
            continue
        rows = []
        for _, p in zv.iterrows():
            life, unit = int(p["shelf_life_days"]), escape(p["unit"])
            mine = lots[lots["product_id"] == p["id"]].sort_values("in_date")
            tag_ = (f'<span class="sk-ztag {"cold" if life < LONG_LIFE_DAYS else "dry"}">'
                    f'{escape(storage_class(life))}</span>')
            if mine.empty:
                countdown = '<span class="sk-cd none">–</span><span class="sk-sub">không có lô nào</span>'
                lot_html = '<div class="sk-none">Không còn hàng trong kho</div>'
                status = '<span class="sk-pill neutral">Hết hàng</span><br><span class="sk-sub">Nhập lô mới; ghi ngày nhập để tính hạn.</span>'
            else:
                first = mine.sort_values("days_left").iloc[0]
                left = int(first["days_left"])
                big = f"Quá hạn {-left}" if left < 0 else ("Hôm nay" if left == 0 else f"{left}")
                more = f" · còn {len(mine) - 1} lô khác" if len(mine) > 1 else ""
                countdown = (f'<span class="sk-cd {first["state"]}">{big} <small>{"ngày" if left else "hết hạn"}</small></span>'
                             f'<span class="sk-sub">hết hạn {first["expiry"]:%d/%m/%Y}<br>lô nhập {first["in_date"]:%d/%m}{more}</span>')
                lot_html = "".join(
                    f'<div class="sk-lot"><div class="lt"><span><b>Lô {l["in_date"]:%d/%m}</b> · {fmt_qty(l["qty"])} {unit}</span>'
                    f'<span>đã lưu <b>{int(l["stored"])}</b> ngày · còn <b class="t-{l["state"]}">{int(l["days_left"])} ngày</b></span></div>'
                    f'<div class="sk-track"><i class="{l["state"]}" style="width:{min(max(l["stored"] / life, 0), 1) * 100:.1f}%"></i></div></div>'
                    for _, l in mine.iterrows())
                cls, label, todo = LOT_STATE[p["worst"]]
                status = f'<span class="sk-pill {cls}">{label}</span><br><span class="sk-sub">{todo}</span>'
            note = escape(p["storage_note"] or "") or '<span class="sk-sub">Chưa ghi điều kiện bảo quản</span>'
            rows.append(
                f'<tr><td><b>{escape(p["name"])}</b><br>{tag_}</td><td>{note}</td>'
                f'<td><b>{life} ngày</b><br><span class="sk-sub">{approx_life(life)}tính từ ngày nhập</span></td>'
                f'<td class="sk-cdcell">{countdown}</td><td>{lot_html}</td><td>{status}</td></tr>')
        with st.container(border=True, key=f"card_zone_{ZONES.index(zone)}"):
            kind = "hàng mau hỏng" if zone == ZONE_COLD else ("hàng đông lạnh" if zone == ZONE_FROZEN else "hàng để lâu được")
            st.markdown(f"#### {zone} <span style='font-weight:400;font-size:15px;color:{MUTED}'>· "
                        f"{len(zv)} mặt hàng · {kind}</span>", unsafe_allow_html=True)
            st.html('<div class="sk-wrap"><table class="sk-table sk-fixed"><colgroup><col style="width:13%"><col style="width:15%">'
                    '<col style="width:10%"><col style="width:12%"><col style="width:34%"><col style="width:16%"></colgroup>'
                    '<thead><tr><th>Sản phẩm</th><th>Điều kiện bảo quản</th><th>Thời gian bảo quản tối đa</th>'
                    '<th>Còn bao nhiêu ngày hết hạn</th><th>Các lô đang trong kho (thanh = đã lưu / hạn dùng)</th>'
                    f'<th>Trạng thái · việc cần làm</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    st.caption("Điều kiện và khu bảo quản sửa ở trang Sản phẩm & danh mục. Hạn dùng tính từ ngày nhập của từng lô "
               "(nhập trước – xuất trước).")


MANAGER_COLORS = ["#14532D", "#1D4ED8", "#B45309", "#6B21A8", "#0E7490", "#9F1239"]


def manager_remark(row, prev) -> str:
    parts = []
    bad = [k for k in kpi.KPI_DEFS if kpi.evaluate(k, row[k]) != kpi.GOOD]
    if prev is not None:
        def gain(k):
            d = row[k] - prev[k]
            return (d if kpi.KPI_DEFS[k]["higher"] else -d) / max(abs(kpi.KPI_DEFS[k]["target"]), 1)
        best = max(kpi.KPI_DEFS, key=gain)
        worst = min(kpi.KPI_DEFS, key=gain)
        if gain(best) > 1e-9:
            parts.append(f"Cải thiện nhiều nhất: <b>{kpi.KPI_DEFS[best]['label'].lower()}</b> "
                         f"({kpi.fmt_value(best, prev[best])} → {kpi.fmt_value(best, row[best])}).")
        if bad:
            k = bad[0]
            parts.append(f"Bị trừ điểm ở <b>{kpi.KPI_DEFS[k]['label'].lower()}</b>: {kpi.fmt_value(k, row[k])} "
                         f"(tiêu chuẩn {kpi.standard_text(k).split(' · ')[0].replace('Đạt ', '')}).")
        elif gain(worst) < -1e-9:
            parts.append(f"Cần chú ý: <b>{kpi.KPI_DEFS[worst]['label'].lower()}</b> xấu đi "
                         f"({kpi.fmt_value(worst, prev[worst])} → {kpi.fmt_value(worst, row[worst])}).")
    elif bad:
        parts.append("Chỉ số chưa đạt: " + ", ".join(kpi.KPI_DEFS[k]["label"].lower() for k in bad) + ".")
    return " ".join(parts) or "Tất cả chỉ số đều đạt tiêu chuẩn."


def page_kpi_managers() -> None:
    assigned = cats.dropna(subset=["manager_id"])
    groups = {}
    for _, c in assigned.iterrows():
        g = groups.setdefault(int(c["manager_id"]), {"name": c["manager"], "cats": []})
        g["cats"].append(c["name"])
    if not USER["is_admin"]:
        groups = {k: v for k, v in groups.items() if k == USER["id"]}

    q_all = cached_quarterly(products, tx, STOCKTAKES)
    if q_all.empty:
        page_head("KPI người quản lý kho", "Chưa có dữ liệu.")
        return
    periods = list(q_all.index)
    top_l, top_r = st.columns([2, 1], vertical_alignment="bottom")
    sel = top_r.selectbox("Quý đánh giá", periods, index=len(periods) - 1, key="kpi_mgr_q")
    with top_l:
        page_head("KPI người quản lý kho",
                  "Đánh giá kết quả công việc của từng người quản lý, tính từ dữ liệu các danh mục họ phụ trách. "
                  "Sản phẩm chỉ là dữ liệu đầu vào, không phải đối tượng bị chấm điểm.")
    if not groups:
        if USER["is_admin"]:
            st.info("Chưa giao danh mục cho người quản lý nào. Vào **Sản phẩm & danh mục → Người quản lý phụ trách** "
                    "để phân công; trong lúc chờ, xem trang **KPI toàn kho**.")
        else:
            st.info("Bạn chưa được giao danh mục nào nên chưa có KPI cá nhân. Xem trang **KPI toàn kho**.")
        return

    i = periods.index(sel)
    data = {}
    for uid, g in groups.items():
        pids = products.loc[products["category"].isin(g["cats"]), "id"]
        p_sub, t_sub = products[products["id"].isin(pids)], tx[tx["product_id"].isin(pids)]
        c_sub = STOCKTAKES[STOCKTAKES["product_id"].isin(pids)]
        q = cached_quarterly(p_sub, t_sub, c_sub)
        if sel not in q.index:
            continue
        j = list(q.index).index(sel)
        data[uid] = dict(g, q=q, row=q.loc[sel], prev=q.iloc[j - 1] if j > 0 else None,
                         products=p_sub, tx=t_sub, counts=c_sub, n=len(p_sub))
    if not data:
        st.info("Các danh mục được giao chưa có dữ liệu trong quý này.")
        return
    order = sorted(data, key=lambda u: -data[u]["row"]["score"])
    colors = {u: MANAGER_COLORS[k % len(MANAGER_COLORS)] for k, u in enumerate(sorted(data))}

    def initials(name: str) -> str:
        w = (name or "?").split()
        return (w[0][:1] + (w[-1][:1] if len(w) > 1 else "")).upper()

    cards = []
    for rank, uid in enumerate(order, 1):
        d = data[uid]
        row, prev = d["row"], d["prev"]
        letter, text = kpi.grade(row["score"])
        sts = [kpi.evaluate(k, row[k]) for k in kpi.KPI_DEFS]
        chips = [f'<span class="sk-pill ok">{sts.count(kpi.GOOD)} / {len(sts)} chỉ số đạt</span>']
        if sts.count(kpi.WARN):
            chips.append(f'<span class="sk-pill low">{sts.count(kpi.WARN)} cảnh báo</span>')
        if sts.count(kpi.BAD):
            chips.append(f'<span class="sk-pill out">{sts.count(kpi.BAD)} chưa đạt</span>')
        if prev is not None:
            delta = row["score"] - prev["score"]
            chips.append(f'<span class="sk-pill {"ok" if delta > 0 else "out" if delta < 0 else "neutral"}">'
                         f'{"▲ +" if delta > 0 else "▼ " if delta < 0 else ""}{delta:.0f} điểm so với {periods[i - 1].split(" ")[0]}</span>')
        if row["counts"]:
            chips.append(f'<span class="sk-pill neutral">Kiểm kê: {int(row["counts_ok"])} / {int(row["counts"])} lần khớp sổ</span>')
        first_q = d["q"].iloc[0]
        if len(d["q"]) > 1:
            chips.append(f'<span class="sk-pill neutral">{d["q"].index[0].split(" ")[0]}: {first_q["score"]:.0f} '
                         f'({first_q["grade"]}) → {sel.split(" ")[0]}: {row["score"]:.0f} ({letter})</span>')
        cards.append(f"""<section class="sk-card sk-person">
<div class="av" style="background:{colors[uid]}">{escape(initials(d['name']))}</div>
<div class="who"><div class="rk">{f"Hạng {rank} / {len(order)}" if USER["is_admin"] else "KPI của bạn"}</div><div class="nm">{escape(d['name'] or '')}</div>
<div class="sk-sub">Phụ trách: {escape(' · '.join(d['cats']))} ({d['n']} mặt hàng)</div></div>
<div class="sc"><div class="big">{row['score']:.0f} <small>/ 100</small></div>
<span class="gr" style="background:{GRADE_COLOR[letter]}">Loại {letter} · {text}</span></div>
<div class="chips">{''.join(chips)}</div>
<div class="rm"><b>Nhận xét:</b> {manager_remark(row, prev)}</div></section>""")
    st.html(f'<div class="sk-people">{"".join(cards)}</div>')

    with st.container(border=True, key="card_mgr_table"):
        st.markdown(f"#### So sánh chỉ số giữa các người quản lý · {sel}")
        head = ["Tiêu chí", "Chỉ số (Index)", "Tiêu chuẩn (Đạt)"] + [escape(data[u]["name"] or "") for u in order]
        rows = []
        for group in kpi.CRITERIA:
            keys = [k for k, dd in kpi.KPI_DEFS.items() if dd["group"] == group]
            for j, k in enumerate(keys):
                dd = kpi.KPI_DEFS[k]
                crit = f'<td rowspan="{len(keys)}"><b>{escape(group)}</b></td>' if j == 0 else ""
                cells = []
                for u in order:
                    row, prev = data[u]["row"], data[u]["prev"]
                    s_ = kpi.evaluate(k, row[k])
                    ch = ""
                    if prev is not None:
                        delta = row[k] - prev[k]
                        good = delta > 1e-9 if dd["higher"] else delta < -1e-9
                        bad = delta < -1e-9 if dd["higher"] else delta > 1e-9
                        val = (f"{delta:+.1f}" if dd["fmt"] != "int" else f"{delta:+.0f}").replace(".", ",")
                        ch = (f'<span class="sk-up">▲ {val}</span>' if good else
                              f'<span class="sk-down">▼ {val}</span>' if bad else '<span class="sk-sub">= 0</span>')
                    cells.append(f'<td><b>{kpi.fmt_value(k, row[k])}</b> {tag(s_, KPI_CLS[s_])} {ch}</td>')
                std = kpi.standard_text(k).split(" · ")[0].replace("Đạt ", "")
                rows.append(f'<tr>{crit}<td>{escape(dd["label"])}</td><td><span class="sk-sub">{escape(std)}</span></td>'
                            f'{"".join(cells)}</tr>')
        html_table(head, rows)
        st.caption("Mũi tên so với quý trước: ▲ xanh = cải thiện, ▼ đỏ = xấu đi. "
                   "Điểm = Σ trọng số × (Đạt 100% · Cảnh báo 60% · Chưa đạt 20%).")

    a, b = st.columns([1.15, 1])
    with a, st.container(border=True, key="card_mgr_trend"):
        fig = go.Figure()
        for u in order:
            q = data[u]["q"]
            fig.add_bar(x=[p.split(" ")[0] for p in q.index], y=q["score"], name=data[u]["name"],
                        marker_color=colors[u], text=[f"{v:.0f}" for v in q["score"]],
                        textposition="inside", insidetextanchor="end", textfont=dict(color="#FFFFFF"))
        fig.add_hline(y=85, line_dash="dash", line_color="#2F7D53", annotation_text="Loại A (85)",
                      annotation_position="top left")
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(plot_layout(fig, "Điểm KPI từng người qua các quý", barmode="group",
                                    yaxis_title="điểm"), width="stretch")
    with b, st.container(border=True, key="card_mgr_plan"):
        st.markdown("#### Phương án cải tiến theo từng người")
        rows = []
        for u in sorted(order, key=lambda u: data[u]["row"]["score"]):
            d = data[u]
            plans = kpi.improvement_plan(d["products"], d["tx"], d["row"], d["prev"],
                                         cached_daily(d["products"], d["tx"]), d["counts"])
            if not plans:
                rows.append(f'<tr><td><b>{escape(d["name"] or "")}</b><br>{tag("Theo dõi", "neutral")}</td>'
                            f'<td>Tất cả chỉ số đạt và không xấu đi. Duy trì cách làm hiện tại.</td></tr>')
                continue
            p = plans[0]
            items = f' (mặt hàng: {escape(", ".join(p["items"]))})' if p["items"] else ""
            others = f'<br><span class="sk-sub">Thêm {len(plans) - 1} chỉ số cần theo dõi.</span>' if len(plans) > 1 else ""
            rows.append(f'<tr><td><b>{escape(d["name"] or "")}</b><br>{tag(p["priority"] if p["priority"] == "Theo dõi" else "Ưu tiên " + p["priority"].lower(), PRIORITY_CLS[p["priority"]])}</td>'
                        f'<td><b>{escape(p["label"])}</b>{items}: {escape(p["action"])}{others}</td></tr>')
        html_table(["Người", "Việc cần làm"], rows)
        st.caption("Người quản lý chỉ thấy KPI của mình; quản trị viên xem được bảng xếp hạng cả kho.")


def page_count() -> None:
    page_head("Kiểm kê", "Đếm số lượng thực tế và đối chiếu với sổ sách. Lệch sổ thì web tự lập phiếu điều chỉnh "
                         "để tồn kho khớp thực tế; kết quả tính vào KPI độ chính xác tồn kho.")
    mine = stock[stock["id"].isin(MY_PIDS)].sort_values("name")
    counts = STOCKTAKES[STOCKTAKES["product_id"].isin(MY_PIDS)]
    if mine.empty:
        st.info("Chưa có sản phẩm nào bạn được giao phụ trách. Nhờ quản trị viên phân công danh mục.")
        return
    q_now = pd.Timestamp(dt.date.today()).to_period("Q") if counts.empty else counts["date"].max().to_period("Q")
    cq = counts[counts["date"].dt.to_period("Q") == q_now]
    acc, ok, n = kpi.accuracy_of(cq, q_now.start_time, q_now.end_time)
    miss = counts[counts["diff"].abs() > counts["book_qty"].abs() * kpi.COUNT_TOLERANCE + 1e-9]
    loss = float((-miss["diff"].clip(upper=0) * miss["price"]).sum())
    d = kpi.KPI_DEFS["accuracy"]
    stat_cards([
        (f"Độ chính xác Q{q_now.quarter}/{q_now.year}", f"{acc:.0f}%".replace(".", ","),
         "" if acc >= d["target"] else "low" if acc >= d["warn"] else "out", f"tiêu chuẩn ≥ {d['target']}%"),
        ("Lần kiểm kê trong quý", f"{n}", "", f"{ok} lần khớp sổ"),
        ("Lần lệch sổ (tất cả)", f"{len(miss)}", "low" if len(miss) else "", f"trên {len(counts)} lần kiểm kê"),
        ("Giá trị hao hụt qua kiểm kê", fmt_money(loss), "out" if loss else "", "hàng thiếu so với sổ"),
    ])

    left, right = st.columns([1, 1.4], gap="large")
    with left, st.container(border=True, key="card_count_form"):
        st.markdown("#### Phiếu kiểm kê")
        by_id = mine.set_index("id")
        pid = st.selectbox("Sản phẩm", by_id.index.tolist(),
                           format_func=lambda i: f"{by_id.at[i, 'name']} — sổ: {fmt_qty(by_id.at[i, 'quantity'])} "
                                                 f"{by_id.at[i, 'unit']}", key="count_pid")
        p = by_id.loc[pid]
        book = float(p["quantity"])
        a, b = st.columns(2)
        counted = a.number_input(f"Đếm thực tế ({p['unit']})", min_value=0.0, value=book, format="%g",
                                 step=1.0 if p["unit"] in COUNT_UNITS else 0.1, key=f"count_{pid}")
        day = b.date_input("Ngày kiểm kê", value=dt.date.today(), format="DD/MM/YYYY", key="count_day")
        note = st.text_input("Ghi chú", placeholder="Ví dụ: kiểm kê cuối tháng, hàng rơi vỡ", key="count_note")
        diff = round(counted - book, 3)
        cls = "" if abs(diff) <= abs(book) * kpi.COUNT_TOLERANCE + 1e-9 else "bad"
        st.html(f"""<dl class="sk-preview">
<div><dt>Tồn trên sổ</dt><dd>{fmt_qty(book)} {escape(p['unit'])}</dd></div>
<div><dt>Chênh lệch</dt><dd class="{cls}">{"+" if diff > 0 else ""}{fmt_qty(diff)} {escape(p['unit'])}</dd></div>
<div><dt>Giá trị chênh lệch</dt><dd class="{cls}">{fmt_money(diff * float(p['price']))}</dd></div></dl>""")
        if st.button("Ghi kết quả kiểm kê", type="primary", width="stretch"):
            try:
                d_ = db.add_stocktake(conn, int(pid), counted, day, note, created_by=USER["username"])
                msg = "khớp sổ sách" if abs(d_) < 1e-9 else f"lệch {'+' if d_ > 0 else ''}{fmt_qty(d_)} {p['unit']}, đã lập phiếu điều chỉnh"
                notify(f"Đã ghi kiểm kê {p['name']}: {msg}.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with right, st.container(border=True, key="card_count_list"):
        h_, t_ = st.columns([3, 2], vertical_alignment="center")
        h_.markdown("#### Kiểm kê gần đây")
        only_off = t_.toggle("Chỉ xem lần lệch sổ", key="count_only_off")
        shown = counts
        if only_off:
            shown = counts[(counts["diff"].abs() > counts["book_qty"].abs() * kpi.COUNT_TOLERANCE + 1e-9)]
        rows = []
        for _, r in shown.head(15).iterrows():
            off = abs(r["diff"]) > abs(r["book_qty"]) * kpi.COUNT_TOLERANCE + 1e-9
            dtxt = (f'{"+" if r["diff"] > 0 else ""}{fmt_qty(r["diff"])}' if r["diff"] else "0")
            rows.append(f'<tr><td class="nowrap">{r["date"]:%d/%m/%Y}</td>'
                        f'<td><b>{escape(r["product"])}</b><br><span class="sk-sub">sổ {fmt_qty(r["book_qty"])} · '
                        f'thực tế {fmt_qty(r["counted_qty"])} {escape(r["unit"])} · {escape(r["created_by"] or "")}</span></td>'
                        f'<td class="r">{dtxt}</td>'
                        f'<td>{tag("Lệch sổ", "out") if off else tag("Khớp", "ok")}</td></tr>')
        html_table(["Ngày", "Sản phẩm · người kiểm", "Chênh lệch", "Kết quả"], rows,
                   right={2}, empty="Chưa có lần kiểm kê nào.", cls="sk-compact")


def page_abc() -> None:
    page_head("Phân tích ABC & vị trí kệ",
              "Xếp mặt hàng theo giá trị xuất: nhóm A (80% giá trị đầu tiên) lấy nhiều nhất nên đặt ở dãy kệ gần "
              "cửa xuất; B tới 95%; C còn lại. Danh sách lấy hàng đi theo thứ tự kệ.")
    abc = inventory.abc_table(stock, tx)
    if abc["out_value"].sum() <= 0:
        st.info("Chưa có dữ liệu xuất kho.")
        return
    n = abc["abc"].value_counts()
    share = abc.groupby("abc")["share"].sum()
    stat_cards([(f"Nhóm {g}", f"{int(n.get(g, 0))} <small>mặt hàng</small>", "",
                 f"{share.get(g, 0):.0f}% giá trị xuất".replace(".", ",")) for g in "ABC"]
               + [("Cần đổi kệ", f"{int(((abc['abc'] == 'A') & ~abc['shelf_location'].fillna('').str.match(r'^[AM]')).sum())}"
                   " <small>mặt hàng A</small>", "low", "nhóm A chưa ở dãy A / kho mát")])
    a, b = st.columns([1.3, 1])
    with a, st.container(border=True, key="card_pareto"):
        fig = go.Figure()
        colors = {"A": ACCENT, "B": "#1D4ED8", "C": "#9DB8AA"}
        fig.add_bar(x=abc["name"], y=abc["share"], marker_color=[colors[g] for g in abc["abc"]], name="% giá trị")
        fig.add_scatter(x=abc["name"], y=abc["cum_share"], mode="lines+markers", name="% lũy kế",
                        line=dict(color=OUT_COLOR), yaxis="y2")
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 105], title="% lũy kế"))
        st.plotly_chart(plot_layout(fig, "Biểu đồ Pareto giá trị xuất", height=380, yaxis_title="% giá trị",
                                    xaxis_tickangle=-45), width="stretch")
    with b, st.container(border=True, key="card_abc_rule"):
        st.markdown("#### Gợi ý bố trí kệ")
        st.markdown("- **Dãy A** (sát cửa xuất): hàng nhóm **A**\n- **Dãy B–C**: nhóm **B**\n- **Dãy D–E** (xa cửa): nhóm **C**\n"
                    "- **Kho mát (M)**: giữ nguyên cho hàng mau hỏng\n\nĐổi vị trí kệ ở trang *Sản phẩm & danh mục*.")
    want = {"A": "A", "B": "B–C", "C": "D–E"}

    def pct(v):
        return f"{v:.1f}%".replace(".", ",")
    rows = []
    for _, r in abc.iterrows():
        loc = (r["shelf_location"] or "").upper()
        row_ = loc[:1]
        ok = loc.startswith("M") or (r["abc"] == "A" and row_ == "A") or (r["abc"] == "B" and row_ in "BC" and row_) \
            or (r["abc"] == "C" and row_ in "DE" and row_)
        hint = tag("Đúng chỗ", "ok") if ok else tag(f"→ dãy {want[r['abc']]}", "low")
        rows.append(f'<tr><td><b>{r["abc"]}</b></td><td><b>{escape(r["name"])}</b><br>'
                    f'<span class="sk-sub">{escape(r["category"])}</span></td>'
                    f'<td class="r">{fmt_money(r["out_value"])}</td><td class="r">{pct(r["share"])}</td>'
                    f'<td class="r">{pct(r["cum_share"])}</td><td class="r">{int(r["out_lines"])}</td>'
                    f'<td><b>{escape(loc or "–")}</b></td><td>{hint}</td></tr>')
    with st.container(border=True, key="card_abc_table"):
        html_table(["Nhóm", "Sản phẩm", "Giá trị xuất", "% giá trị", "% lũy kế", "Lượt xuất", "Kệ hiện tại", "Gợi ý"],
                   rows, right={2, 3, 4, 5})


pg_stock = st.Page(page_stock, title="Tồn kho", icon=":material/inventory_2:",
                   url_path="ton-kho", default=True)
pg_tx = st.Page(page_tx, title="Phiếu kho", icon=":material/swap_vert:", url_path="phieu-kho")
pg_products = st.Page(page_products, title="Sản phẩm & danh mục", icon=":material/sell:",
                      url_path="san-pham")
pg_report = st.Page(page_report, title="Báo cáo", icon=":material/bar_chart:", url_path="bao-cao")
pg_history = st.Page(page_history, title="Lịch sử giao dịch", icon=":material/receipt_long:",
                     url_path="lich-su")

pg_account = st.Page(page_account, title="Tài khoản", icon=":material/manage_accounts:",
                     url_path="tai-khoan")

with st.sidebar:
    st.caption(f"Đang đăng nhập: **{USER['full_name']}** ({USER['username']})"
               + f" · {auth.ROLE_LABEL[USER['role']].lower()}")
    if st.button("Đăng xuất", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()

pg_daily = st.Page(page_daily, title="Báo cáo cuối ngày", icon=":material/today:", url_path="cuoi-ngay")
pg_kpi = st.Page(page_kpi, title="KPI toàn kho", icon=":material/workspace_premium:", url_path="kpi")
pg_kpi_mgr = st.Page(page_kpi_managers, title="KPI người quản lý kho", icon=":material/badge:",
                     url_path="kpi-nguoi-quan-ly")
pg_storage = st.Page(page_storage, title="Thời hạn bảo quản", icon=":material/hourglass_bottom:",
                     url_path="thoi-han-bao-quan")
pg_risk = st.Page(page_risk, title="Quản lý rủi ro", icon=":material/warning:", url_path="rui-ro")

pg_count = st.Page(page_count, title="Kiểm kê", icon=":material/fact_check:", url_path="kiem-ke")

pg_abc = st.Page(page_abc, title="Phân tích ABC & kệ", icon=":material/stacked_bar_chart:", url_path="abc")

reports = [pg_daily, pg_kpi_mgr, pg_kpi, pg_report, pg_abc, pg_risk]
if USER["is_admin"]:
    pages = {"Kho hàng": [pg_stock, pg_storage, pg_tx, pg_count, pg_products, pg_history],
             "Báo cáo & đánh giá": reports, "Hệ thống": [pg_account]}
elif USER["can_write"]:
    pages = {"Kho hàng": [pg_stock, pg_storage, pg_tx, pg_count, pg_history],
             "Báo cáo & đánh giá": reports, "Hệ thống": [pg_account]}
else:
    pages = {"Kho hàng": [pg_stock, pg_storage, pg_history], "Báo cáo & đánh giá": reports,
             "Hệ thống": [pg_account]}
nav = st.navigation(pages, expanded=True)
nav.run()
