# -*- coding: utf-8 -*-
"""
Định nghĩa danh mục mặc định, đơn vị tính, loại giao dịch và quy tắc
đánh giá trạng thái tồn kho.

Muốn đổi quy tắc / màu / đơn vị → chỉ cần sửa file này.
"""

from __future__ import annotations

import math

# Danh mục mặc định (tạo khi khởi tạo cơ sở dữ liệu lần đầu)
DEFAULT_CATEGORIES = [
    ("Sữa & đồ uống", "Sữa tươi, sữa đặc, nước uống đóng chai"),
    ("Lương thực", "Gạo, nếp, mì gói, bún khô"),
    ("Gia vị", "Muối, tiêu, bột ngọt, đường, nước mắm, nước tương"),
    ("Dầu ăn", "Dầu thực vật, dầu đậu nành, dầu mè"),
    ("Đồ khô", "Đậu, hạt, đồ khô đóng gói"),
]

UNCATEGORIZED = "Chưa phân loại"

# Đơn vị tính cho phép
UNITS = ["kg", "g", "lít", "ml", "gói", "chai", "hộp", "lon", "túi", "quả", "cái"]

# Loại giao dịch kho
TX_IN = "in"
TX_OUT = "out"
TX_LABEL = {TX_IN: "Nhập kho", TX_OUT: "Xuất kho"}

# Trạng thái tồn kho
IN_STOCK = "Đủ hàng"
LOW_STOCK = "Sắp hết"
OUT_OF_STOCK = "Hết hàng"
STATUSES = [IN_STOCK, LOW_STOCK, OUT_OF_STOCK]

STATUS_COLOR = {
    IN_STOCK: "#16a34a",      # xanh
    LOW_STOCK: "#d97706",     # cam
    OUT_OF_STOCK: "#dc2626",  # đỏ
}
STATUS_ICON = {IN_STOCK: "🟢", LOW_STOCK: "🟠", OUT_OF_STOCK: "🔴"}


def evaluate_stock(quantity: float, min_stock: float) -> str:
    """Trả về trạng thái tồn kho của một mặt hàng.

    - Hết hàng : tồn kho <= 0
    - Sắp hết  : 0 < tồn kho <= mức tồn tối thiểu
    - Đủ hàng  : tồn kho > mức tồn tối thiểu
    """
    if quantity <= 0:
        return OUT_OF_STOCK
    if quantity <= min_stock:
        return LOW_STOCK
    return IN_STOCK


def fmt_qty(value: float) -> str:
    """20.0 -> '20' ; 1.5 -> '1,5' ; 1200 -> '1.200'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    s = f"{value:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_money(value: float) -> str:
    """32000 -> '32.000 đ'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    return f"{value:,.0f} đ".replace(",", ".")
