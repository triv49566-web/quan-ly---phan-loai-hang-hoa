# -*- coding: utf-8 -*-
"""
Ứng dụng web quản lý & phân loại hàng hóa nhu yếu phẩm (sữa, gạo, muối,
tiêu, dầu ăn, bột ngọt, ...).

Chạy:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import database as db
from src import inventory
from src.catalog import (
    IN_STOCK, LOW_STOCK, OUT_OF_STOCK, STATUSES, STATUS_COLOR, STATUS_ICON,
    TX_IN, TX_LABEL, TX_OUT, UNCATEGORIZED, UNITS, fmt_money, fmt_qty,
)

# ---------------------------------------------------------------------------
# Thiết lập trang
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Quản lý nhu yếu phẩm", page_icon="🛒", layout="wide")

PALETTE = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#0891b2", "#dc2626"]


@st.cache_resource
def _init() -> bool:
    db.init_db()
    return True


_init()
conn = db.connect()


def notify(msg: str, icon: str = "✅") -> None:
    """Lưu thông báo để hiển thị sau khi trang tải lại."""
    st.session_state["_flash"] = (msg, icon)


if "_flash" in st.session_state:
    _msg, _icon = st.session_state.pop("_flash")
    st.toast(_msg, icon=_icon)

cats = db.categories_df(conn)
products = db.products_df(conn)
tx = db.transactions_df(conn)
stock = inventory.stock_table(products, tx)
stock["category"] = stock["category"].fillna(UNCATEGORIZED)
tx["category"] = tx["category"].fillna(UNCATEGORIZED)

# ---------------------------------------------------------------------------
# Sidebar – bộ lọc
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Bộ lọc")
    all_cats = sorted(stock["category"].unique()) if not stock.empty else []
    sel_cats = st.multiselect("Danh mục", all_cats, default=all_cats)
    keyword = st.text_input("Tìm theo tên", placeholder="VD: gạo, sữa...")
    sel_status = st.multiselect("Trạng thái tồn kho", STATUSES, default=STATUSES,
                                format_func=lambda s: f"{STATUS_ICON[s]} {s}")
    st.divider()
    if not tx.empty:
        st.caption(
            "Nguồn: `data/hanghoa.db`\n\n"
            f"- {len(products)} sản phẩm, {len(cats)} danh mục\n"
            f"- {len(tx)} giao dịch "
            f"({tx['date'].min():%d/%m/%Y} → {tx['date'].max():%d/%m/%Y})"
        )

view = stock[stock["category"].isin(sel_cats) & stock["status"].isin(sel_status)]
if keyword.strip():
    view = view[view["name"].str.contains(keyword.strip(), case=False, regex=False)]

# ---------------------------------------------------------------------------
# Tiêu đề
# ---------------------------------------------------------------------------
st.title("🛒 Quản lý & phân loại nhu yếu phẩm")
st.markdown("Theo dõi **tồn kho**, **nhập / xuất hàng** và **phân loại** các mặt hàng "
            "thiết yếu hằng ngày: sữa, gạo, muối, tiêu, dầu ăn, bột ngọt...")

tab_stock, tab_tx, tab_manage, tab_report, tab_history = st.tabs(
    ["📦 Tồn kho", "🔄 Nhập / Xuất kho", "🗂️ Sản phẩm & Danh mục",
     "📈 Báo cáo", "🗃️ Lịch sử giao dịch"]
)


# ===========================================================================
# TAB 1 – TỒN KHO
# ===========================================================================
with tab_stock:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Số mặt hàng", len(view))
    c2.metric("Giá trị tồn kho", fmt_money(view["value"].sum()))
    c3.metric(f"{STATUS_ICON[LOW_STOCK]} Sắp hết", int((view["status"] == LOW_STOCK).sum()))
    c4.metric(f"{STATUS_ICON[OUT_OF_STOCK]} Hết hàng",
              int((view["status"] == OUT_OF_STOCK).sum()))

    if view.empty:
        st.info("Không có sản phẩm nào khớp bộ lọc.")
    else:
        for cat_name, grp in view.groupby("category", sort=True):
            st.markdown(f"#### {cat_name}  ·  {len(grp)} mặt hàng  ·  "
                        f"{fmt_money(grp['value'].sum())}")
            show = pd.DataFrame({
                "Trạng thái": [f"{STATUS_ICON[s]} {s}" for s in grp["status"]],
                "Sản phẩm": grp["name"],
                "Tồn kho": [f"{fmt_qty(q)} {u}" for q, u in zip(grp["quantity"], grp["unit"])],
                "Tồn tối thiểu": [f"{fmt_qty(q)} {u}" for q, u in zip(grp["min_stock"], grp["unit"])],
                "Đơn giá": [f"{fmt_money(p)}/{u}" for p, u in zip(grp["price"], grp["unit"])],
                "Giá trị tồn": [fmt_money(v) for v in grp["value"]],
                f"Xuất {inventory.WINDOW_DAYS} ngày": [
                    f"{fmt_qty(q)} {u}" for q, u in zip(grp["out_window"], grp["unit"])],
                "Đủ dùng (ngày)": [("–" if pd.isna(d) else f"{int(d)}") for d in grp["days_cover"]],
            })
            colors = [STATUS_COLOR[s] for s in grp["status"]]
            styler = show.style.apply(
                lambda col: [f"color:{c};font-weight:600" for c in colors],
                subset=["Trạng thái"])
            st.dataframe(styler, hide_index=True, width="stretch")

        export = view[["name", "category", "unit", "quantity", "min_stock", "price",
                       "value", "out_window", "days_cover", "status"]]
        st.download_button("⬇️ Tải bảng tồn kho (CSV)",
                           export.to_csv(index=False).encode("utf-8-sig"),
                           file_name="ton_kho.csv", mime="text/csv")
    st.caption(f"🟢 {IN_STOCK} – 🟠 {LOW_STOCK} (≤ mức tồn tối thiểu) – 🔴 {OUT_OF_STOCK}. "
               f"“Đủ dùng” = tồn kho ÷ lượng xuất bình quân/ngày trong "
               f"{inventory.WINDOW_DAYS} ngày gần nhất.")


# ===========================================================================
# TAB 2 – NHẬP / XUẤT KHO
# ===========================================================================
with tab_tx:
    if products.empty:
        st.info("Chưa có sản phẩm. Hãy thêm ở tab **Sản phẩm & Danh mục**.")
    else:
        st.subheader("Ghi nhận nhập / xuất kho")
        by_id = stock.set_index("id")
        pid = st.selectbox(
            "Sản phẩm", stock["id"].tolist(),
            format_func=lambda i: (f"{by_id.at[i, 'name']}  —  tồn "
                                   f"{fmt_qty(by_id.at[i, 'quantity'])} {by_id.at[i, 'unit']}"),
        )
        p = by_id.loc[pid]
        col1, col2, col3 = st.columns(3)
        tx_type = col1.radio("Loại", [TX_IN, TX_OUT], format_func=TX_LABEL.get,
                             horizontal=True)
        step = 1.0 if p["unit"] in ("gói", "chai", "hộp", "lon", "túi", "quả", "cái") else 0.1
        qty = col2.number_input(f"Số lượng ({p['unit']})", min_value=0.0, step=step,
                                key=f"qty_{pid}")
        price = col3.number_input("Đơn giá (đ / đơn vị)", min_value=0.0, step=1000.0,
                                  value=float(p["price"]), key=f"price_{pid}")
        col4, col5 = st.columns([1, 2])
        tx_date = col4.date_input("Ngày", value=dt.date.today(), format="DD/MM/YYYY")
        note = col5.text_input("Ghi chú", placeholder="VD: nhập từ NCC A, bán lẻ...")
        if qty > 0:
            st.caption(f"Thành tiền: **{fmt_money(qty * price)}**")
        if st.button("💾 Ghi nhận", type="primary"):
            try:
                db.add_transaction(conn, int(pid), tx_type, qty, price, tx_date, note)
                notify(f"{TX_LABEL[tx_type]} {fmt_qty(qty)} {p['unit']} “{p['name']}”.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

        st.divider()
        st.subheader("Giao dịch gần đây")
        recent = tx.head(15)
        st.dataframe(pd.DataFrame({
            "Ngày": recent["date"].dt.strftime("%d/%m/%Y"),
            "Loại": recent["type"].map(TX_LABEL),
            "Sản phẩm": recent["product"],
            "Số lượng": [f"{fmt_qty(q)} {u}" for q, u in zip(recent["quantity"], recent["unit"])],
            "Thành tiền": [fmt_money(q * pr) for q, pr in zip(recent["quantity"], recent["unit_price"])],
            "Ghi chú": recent["note"],
        }), hide_index=True, width="stretch")


# ===========================================================================
# TAB 3 – SẢN PHẨM & DANH MỤC
# ===========================================================================
cat_options = [None] + cats["id"].tolist()
cat_name_of = dict(zip(cats["id"], cats["name"]))


def cat_label(cid):
    return UNCATEGORIZED if cid is None else cat_name_of[cid]


with tab_manage:
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("➕ Thêm sản phẩm")
        with st.form("add_product", clear_on_submit=True):
            name = st.text_input("Tên sản phẩm *", placeholder="VD: Gạo ST25")
            a, b = st.columns(2)
            cid = a.selectbox("Danh mục", cat_options, format_func=cat_label)
            unit = b.selectbox("Đơn vị tính *", UNITS)
            a, b, c = st.columns(3)
            price = a.number_input("Đơn giá (đ)", min_value=0.0, step=1000.0)
            min_stock = b.number_input("Tồn tối thiểu", min_value=0.0, step=1.0)
            opening = c.number_input("Tồn đầu kỳ", min_value=0.0, step=1.0)
            note = st.text_input("Ghi chú")
            if st.form_submit_button("Thêm sản phẩm", type="primary"):
                try:
                    db.add_product(conn, name, cid, unit, price, min_stock, note, opening)
                    notify(f"Đã thêm “{name.strip()}”.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        st.divider()
        st.subheader("✏️ Sửa / xóa sản phẩm")
        if products.empty:
            st.info("Chưa có sản phẩm.")
        else:
            prod_by_id = products.set_index("id")
            eid = st.selectbox("Chọn sản phẩm", products["id"].tolist(),
                               format_func=lambda i: prod_by_id.at[i, "name"], key="edit_sel")
            e = prod_by_id.loc[eid]
            cur_cid = None if pd.isna(e["category_id"]) else int(e["category_id"])
            with st.form(f"edit_{eid}"):
                name = st.text_input("Tên sản phẩm *", value=e["name"])
                a, b = st.columns(2)
                cid = a.selectbox("Danh mục", cat_options, format_func=cat_label,
                                  index=cat_options.index(cur_cid))
                unit = b.selectbox("Đơn vị tính *", UNITS,
                                   index=UNITS.index(e["unit"]) if e["unit"] in UNITS else 0)
                a, b = st.columns(2)
                price = a.number_input("Đơn giá (đ)", min_value=0.0, step=1000.0,
                                       value=float(e["price"]))
                min_stock = b.number_input("Tồn tối thiểu", min_value=0.0, step=1.0,
                                           value=float(e["min_stock"]))
                note = st.text_input("Ghi chú", value=e["note"] or "")
                if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                    try:
                        db.update_product(conn, int(eid), name, cid, unit, price, min_stock, note)
                        notify(f"Đã cập nhật “{name.strip()}”.")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))
            confirm = st.checkbox("Tôi muốn xóa sản phẩm này (kèm toàn bộ lịch sử giao dịch)",
                                  key=f"confirm_del_{eid}")
            if st.button("🗑️ Xóa sản phẩm", disabled=not confirm):
                db.delete_product(conn, int(eid))
                notify(f"Đã xóa “{e['name']}”.", "🗑️")
                st.rerun()

    with right:
        st.subheader("🗂️ Danh mục")
        st.dataframe(
            cats.rename(columns={"name": "Danh mục", "description": "Mô tả",
                                 "products": "Số SP"})[["Danh mục", "Mô tả", "Số SP"]],
            hide_index=True, width="stretch")
        with st.form("add_cat", clear_on_submit=True):
            cname = st.text_input("Tên danh mục mới", placeholder="VD: Đồ hộp")
            cdesc = st.text_input("Mô tả")
            if st.form_submit_button("Thêm danh mục"):
                try:
                    db.add_category(conn, cname, cdesc)
                    notify(f"Đã thêm danh mục “{cname.strip()}”.")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
        if not cats.empty:
            did = st.selectbox("Xóa danh mục", cats["id"].tolist(), format_func=cat_label,
                               key="del_cat")
            st.caption("Sản phẩm trong danh mục bị xóa sẽ chuyển sang “Chưa phân loại”.")
            if st.button("🗑️ Xóa danh mục"):
                db.delete_category(conn, int(did))
                notify(f"Đã xóa danh mục “{cat_label(did)}”.", "🗑️")
                st.rerun()


# ===========================================================================
# TAB 4 – BÁO CÁO
# ===========================================================================
def _layout(fig: go.Figure, title: str, height: int = 380, **kw) -> go.Figure:
    fig.update_layout(title=title, height=height, plot_bgcolor="white",
                      margin=dict(l=10, r=10, t=50, b=10), **kw)
    return fig


with tab_report:
    if view.empty:
        st.info("Không có dữ liệu khớp bộ lọc.")
    else:
        summary = inventory.category_summary(view)
        a, b = st.columns(2)

        fig = go.Figure(go.Bar(
            x=summary["category"], y=summary["value"], marker_color=PALETTE[0],
            text=[fmt_money(v) for v in summary["value"]], textposition="outside"))
        a.plotly_chart(_layout(fig, "Giá trị tồn kho theo danh mục", yaxis_title="đ"),
                       width="stretch")

        fig = go.Figure()
        for s in STATUSES:
            if s in summary.columns:
                fig.add_bar(x=summary["category"], y=summary[s], name=f"{STATUS_ICON[s]} {s}",
                            marker_color=STATUS_COLOR[s])
        b.plotly_chart(_layout(fig, "Trạng thái tồn kho theo danh mục", barmode="stack",
                               yaxis_title="số mặt hàng"), width="stretch")

        flow = inventory.monthly_flow(tx[tx["product_id"].isin(view["id"])])
        fig = go.Figure()
        fig.add_bar(x=flow["month"], y=flow["Nhập kho"], name="Nhập kho", marker_color=PALETTE[1])
        fig.add_bar(x=flow["month"], y=flow["Xuất kho"], name="Xuất kho", marker_color=PALETTE[2])
        a.plotly_chart(_layout(fig, "Giá trị nhập / xuất theo tháng", barmode="group",
                               yaxis_title="đ"), width="stretch")

        top = inventory.top_consumed(view).iloc[::-1]
        fig = go.Figure(go.Bar(
            y=top["name"], x=top["out_window"] * top["price"], orientation="h",
            marker_color=PALETTE[3],
            text=[f"{fmt_qty(q)} {u}" for q, u in zip(top["out_window"], top["unit"])],
            textposition="auto"))
        b.plotly_chart(_layout(fig, f"Top xuất nhiều nhất {inventory.WINDOW_DAYS} ngày (theo giá trị)",
                               xaxis_title="đ"), width="stretch")


# ===========================================================================
# TAB 5 – LỊCH SỬ GIAO DỊCH
# ===========================================================================
with tab_history:
    h = tx[tx["product_id"].isin(view["id"])]
    if h.empty:
        st.info("Chưa có giao dịch.")
    else:
        a, b = st.columns([1, 2])
        types = a.multiselect("Loại giao dịch", [TX_IN, TX_OUT], default=[TX_IN, TX_OUT],
                              format_func=TX_LABEL.get)
        dmin, dmax = h["date"].min().date(), h["date"].max().date()
        rng = b.date_input("Khoảng thời gian", value=(dmin, dmax), format="DD/MM/YYYY")
        h = h[h["type"].isin(types)]
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
        st.caption(f"{len(out)} giao dịch · Nhập: "
                   f"{fmt_money(out.loc[h['type'] == TX_IN, 'Thành tiền'].sum())} · Xuất: "
                   f"{fmt_money(out.loc[h['type'] == TX_OUT, 'Thành tiền'].sum())}")
        st.dataframe(out, hide_index=True, width="stretch", height=480,
                     column_config={
                         "Đơn giá": st.column_config.NumberColumn(format="localized"),
                         "Thành tiền": st.column_config.NumberColumn(format="localized"),
                     })
        st.download_button("⬇️ Tải lịch sử (CSV)", out.to_csv(index=False).encode("utf-8-sig"),
                           file_name="lich_su_giao_dich.csv", mime="text/csv")
