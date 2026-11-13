# -*- coding: utf-8 -*-
"""
Lưu trữ dữ liệu bằng SQLite (file data/hanghoa.db).

Lần chạy đầu tiên, cơ sở dữ liệu được tạo và nạp dữ liệu mẫu từ
data/raw/products.csv và data/raw/transactions.csv.
Muốn làm lại từ đầu: xóa file data/hanghoa.db rồi chạy lại app.
"""

from __future__ import annotations

import datetime as dt
import os
import sqlite3

import pandas as pd

from . import catalog
from .catalog import TX_IN, TX_OUT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "hanghoa.db")
RAW_DIR = os.path.join(ROOT, "data", "raw")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    unit        TEXT NOT NULL,
    price       REAL NOT NULL DEFAULT 0,      -- đơn giá tham khảo (đ / đơn vị)
    min_stock   REAL NOT NULL DEFAULT 0,      -- mức tồn tối thiểu để cảnh báo
    note        TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,                -- YYYY-MM-DD
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('in', 'out')),
    quantity    REAL NOT NULL CHECK (quantity > 0),
    unit_price  REAL NOT NULL DEFAULT 0,
    note        TEXT DEFAULT ''
);
"""


# ---------------------------------------------------------------------------
# Kết nối & khởi tạo
# ---------------------------------------------------------------------------
def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | None = None, seed: bool = True) -> None:
    """Tạo bảng (nếu chưa có) và nạp dữ liệu mẫu khi cơ sở dữ liệu còn trống."""
    path = path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            conn.executemany("INSERT INTO categories(name, description) VALUES (?, ?)",
                             catalog.DEFAULT_CATEGORIES)
        if seed and conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            _seed_from_csv(conn)


def _seed_from_csv(conn: sqlite3.Connection) -> None:
    prod_csv = os.path.join(RAW_DIR, "products.csv")
    tx_csv = os.path.join(RAW_DIR, "transactions.csv")
    if not os.path.exists(prod_csv):
        return
    cat_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM categories")}
    products = pd.read_csv(prod_csv, encoding="utf-8-sig").fillna({"note": ""})
    for p in products.itertuples(index=False):
        if p.category not in cat_ids:
            cur = conn.execute("INSERT INTO categories(name) VALUES (?)", (p.category,))
            cat_ids[p.category] = cur.lastrowid
        conn.execute(
            "INSERT INTO products(name, category_id, unit, price, min_stock, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (p.name, cat_ids[p.category], p.unit, float(p.price), float(p.min_stock), p.note))
    if os.path.exists(tx_csv):
        prod_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM products")}
        tx = pd.read_csv(tx_csv, encoding="utf-8-sig").fillna({"note": ""})
        conn.executemany(
            "INSERT INTO transactions(date, product_id, type, quantity, unit_price, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [(t.date, prod_ids[t.product], t.type, float(t.quantity), float(t.unit_price), t.note)
             for t in tx.itertuples(index=False)])


# ---------------------------------------------------------------------------
# Đọc dữ liệu (trả về pandas DataFrame)
# ---------------------------------------------------------------------------
def categories_df(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT c.id, c.name, c.description, COUNT(p.id) AS products "
        "FROM categories c LEFT JOIN products p ON p.category_id = c.id "
        "GROUP BY c.id ORDER BY c.name", conn)


def products_df(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT p.id, p.name, p.category_id, c.name AS category, p.unit, p.price, "
        "p.min_stock, p.note FROM products p "
        "LEFT JOIN categories c ON c.id = p.category_id ORDER BY c.name, p.name", conn)


def transactions_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT t.id, t.date, t.product_id, p.name AS product, c.name AS category, "
        "p.unit, t.type, t.quantity, t.unit_price, t.note FROM transactions t "
        "JOIN products p ON p.id = t.product_id "
        "LEFT JOIN categories c ON c.id = p.category_id "
        "ORDER BY t.date DESC, t.id DESC", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def current_stock(conn: sqlite3.Connection, product_id: int) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE type WHEN 'in' THEN quantity ELSE -quantity END), 0) "
        "FROM transactions WHERE product_id = ?", (product_id,)).fetchone()
    return round(float(row[0]), 3)


# ---------------------------------------------------------------------------
# Ghi dữ liệu (ném ValueError kèm thông báo tiếng Việt khi dữ liệu sai)
# ---------------------------------------------------------------------------
def _check_product(name: str, unit: str, price: float, min_stock: float) -> None:
    if not name.strip():
        raise ValueError("Tên sản phẩm không được để trống.")
    if unit not in catalog.UNITS:
        raise ValueError(f"Đơn vị “{unit}” không hợp lệ.")
    if price < 0 or min_stock < 0:
        raise ValueError("Đơn giá và mức tồn tối thiểu phải ≥ 0.")


def add_category(conn: sqlite3.Connection, name: str, description: str = "") -> None:
    if not name.strip():
        raise ValueError("Tên danh mục không được để trống.")
    try:
        with conn:
            conn.execute("INSERT INTO categories(name, description) VALUES (?, ?)",
                         (name.strip(), description.strip()))
    except sqlite3.IntegrityError:
        raise ValueError(f"Danh mục “{name}” đã tồn tại.") from None


def delete_category(conn: sqlite3.Connection, category_id: int) -> None:
    """Xóa danh mục; sản phẩm bên trong chuyển sang 'Chưa phân loại'."""
    with conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def add_product(conn: sqlite3.Connection, name: str, category_id: int | None, unit: str,
                price: float, min_stock: float, note: str = "",
                opening_qty: float = 0, date: dt.date | None = None) -> int:
    """Thêm sản phẩm; nếu opening_qty > 0 thì ghi luôn một phiếu nhập tồn đầu."""
    _check_product(name, unit, price, min_stock)
    if opening_qty < 0:
        raise ValueError("Số lượng tồn đầu phải ≥ 0.")
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO products(name, category_id, unit, price, min_stock, note)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name.strip(), category_id, unit, price, min_stock, note.strip()))
            pid = cur.lastrowid
            if opening_qty > 0:
                conn.execute(
                    "INSERT INTO transactions(date, product_id, type, quantity, unit_price, note)"
                    " VALUES (?, ?, 'in', ?, ?, 'Tồn đầu kỳ')",
                    ((date or dt.date.today()).isoformat(), pid, opening_qty, price))
    except sqlite3.IntegrityError:
        raise ValueError(f"Sản phẩm “{name}” đã tồn tại.") from None
    return pid


def update_product(conn: sqlite3.Connection, product_id: int, name: str,
                   category_id: int | None, unit: str, price: float,
                   min_stock: float, note: str = "") -> None:
    _check_product(name, unit, price, min_stock)
    try:
        with conn:
            conn.execute(
                "UPDATE products SET name=?, category_id=?, unit=?, price=?, min_stock=?, note=?"
                " WHERE id=?",
                (name.strip(), category_id, unit, price, min_stock, note.strip(), product_id))
    except sqlite3.IntegrityError:
        raise ValueError(f"Sản phẩm “{name}” đã tồn tại.") from None


def delete_product(conn: sqlite3.Connection, product_id: int) -> None:
    """Xóa sản phẩm và toàn bộ lịch sử giao dịch của nó."""
    with conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def add_transaction(conn: sqlite3.Connection, product_id: int, tx_type: str,
                    quantity: float, unit_price: float,
                    date: dt.date | None = None, note: str = "") -> None:
    """Ghi một phiếu nhập / xuất kho. Không cho xuất vượt quá tồn kho."""
    if tx_type not in (TX_IN, TX_OUT):
        raise ValueError("Loại giao dịch không hợp lệ.")
    if quantity <= 0:
        raise ValueError("Số lượng phải lớn hơn 0.")
    if unit_price < 0:
        raise ValueError("Đơn giá phải ≥ 0.")
    if tx_type == TX_OUT:
        stock = current_stock(conn, product_id)
        if quantity > stock:
            raise ValueError(f"Không đủ hàng để xuất: chỉ còn {catalog.fmt_qty(stock)}.")
    with conn:
        conn.execute(
            "INSERT INTO transactions(date, product_id, type, quantity, unit_price, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ((date or dt.date.today()).isoformat(), product_id, tx_type,
             quantity, unit_price, note.strip()))
