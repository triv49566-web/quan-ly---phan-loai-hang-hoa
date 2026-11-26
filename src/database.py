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

from . import auth, catalog
from .catalog import ALL_TX_TYPES, TX_ADJ_MINUS, TX_ADJ_PLUS, TX_DISPOSE, TX_IN, TX_OUT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "hanghoa.db")
RAW_DIR = os.path.join(ROOT, "data", "raw")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    manager_id  INTEGER REFERENCES users(id) ON DELETE SET NULL  -- người quản lý phụ trách
);
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    unit        TEXT NOT NULL,
    price       REAL NOT NULL DEFAULT 0,      -- đơn giá tham khảo (đ / đơn vị)
    min_stock   REAL NOT NULL DEFAULT 0,      -- mức tồn tối thiểu (lượng dự trữ) để cảnh báo
    shelf_life_days INTEGER NOT NULL DEFAULT 365,  -- hạn sử dụng tính từ ngày nhập
    storage_zone TEXT DEFAULT '',             -- khu bảo quản (trống = tự chọn theo hạn dùng)
    storage_note TEXT DEFAULT '',             -- điều kiện bảo quản
    note        TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,                -- YYYY-MM-DD
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('in', 'out', 'dispose', 'adj_plus', 'adj_minus')),
    quantity    REAL NOT NULL CHECK (quantity > 0),
    unit_price  REAL NOT NULL DEFAULT 0,
    note        TEXT DEFAULT '',
    created_by  TEXT DEFAULT ''                -- tên tài khoản người lập phiếu
);
CREATE TABLE IF NOT EXISTS stocktakes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    book_qty    REAL NOT NULL,                -- tồn trên sổ lúc kiểm kê
    counted_qty REAL NOT NULL CHECK (counted_qty >= 0),  -- tồn đếm thực tế
    note        TEXT DEFAULT '',
    created_by  TEXT DEFAULT ''
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
        conn.executescript(auth.SCHEMA)   # bảng tài khoản (danh mục tham chiếu người quản lý)
        conn.executescript(SCHEMA)
        _migrate(conn)
        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            conn.executemany("INSERT INTO categories(name, description) VALUES (?, ?)",
                             catalog.DEFAULT_CATEGORIES)
        if seed and conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            _seed_from_csv(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Nâng cấp file dữ liệu tạo từ phiên bản cũ (thiếu hạn dùng / phiếu hủy hàng)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
    if "shelf_life_days" not in cols:
        conn.execute("ALTER TABLE products ADD COLUMN shelf_life_days INTEGER NOT NULL DEFAULT 365")
    added = False
    for col in ("storage_zone", "storage_note"):
        if col not in cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT DEFAULT ''")
            added = True
    if added:
        _fill_storage_from_csv(conn)
    cat_cols = {r["name"] for r in conn.execute("PRAGMA table_info(categories)")}
    if "manager_id" not in cat_cols:
        conn.execute("ALTER TABLE categories ADD COLUMN manager_id INTEGER "
                     "REFERENCES users(id) ON DELETE SET NULL")
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'transactions'").fetchone()[0]
    if "adj_plus" not in sql:
        conn.executescript("""
            ALTER TABLE transactions RENAME TO transactions_old;
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK (type IN ('in', 'out', 'dispose', 'adj_plus', 'adj_minus')),
                quantity REAL NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL DEFAULT 0,
                note TEXT DEFAULT '',
                created_by TEXT DEFAULT ''
            );
            INSERT INTO transactions(id, date, product_id, type, quantity, unit_price, note)
                SELECT id, date, product_id, type, quantity, unit_price, note FROM transactions_old;
            DROP TABLE transactions_old;
        """)


def _fill_storage_from_csv(conn: sqlite3.Connection) -> None:
    """File dữ liệu cũ: lấy khu / điều kiện bảo quản mẫu theo tên sản phẩm."""
    prod_csv = os.path.join(RAW_DIR, "products.csv")
    if not os.path.exists(prod_csv):
        return
    df = pd.read_csv(prod_csv, encoding="utf-8-sig")
    if "storage_note" not in df.columns:
        return
    df = df.fillna({"storage_zone": "", "storage_note": ""})
    conn.executemany(
        "UPDATE products SET storage_zone = ?, storage_note = ? WHERE name = ? AND storage_note = ''",
        [(r.storage_zone, r.storage_note, r.name) for r in df.itertuples(index=False)])


def _seed_from_csv(conn: sqlite3.Connection) -> None:
    prod_csv = os.path.join(RAW_DIR, "products.csv")
    tx_csv = os.path.join(RAW_DIR, "transactions.csv")
    if not os.path.exists(prod_csv):
        return
    cat_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM categories")}
    products = pd.read_csv(prod_csv, encoding="utf-8-sig").fillna(
        {"note": "", "storage_zone": "", "storage_note": ""})
    for p in products.itertuples(index=False):
        if p.category not in cat_ids:
            cur = conn.execute("INSERT INTO categories(name) VALUES (?)", (p.category,))
            cat_ids[p.category] = cur.lastrowid
        shelf = int(getattr(p, "shelf_life_days", 365))
        conn.execute(
            "INSERT INTO products(name, category_id, unit, price, min_stock, shelf_life_days,"
            " storage_zone, storage_note, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p.name, cat_ids[p.category], p.unit, float(p.price), float(p.min_stock), shelf,
             getattr(p, "storage_zone", ""), getattr(p, "storage_note", ""), p.note))
    if os.path.exists(tx_csv):
        prod_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM products")}
        tx = pd.read_csv(tx_csv, encoding="utf-8-sig").fillna({"note": "", "created_by": ""})
        conn.executemany(
            "INSERT INTO transactions(date, product_id, type, quantity, unit_price, note, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(t.date, prod_ids[t.product], t.type, float(t.quantity), float(t.unit_price), t.note,
              getattr(t, "created_by", "")) for t in tx.itertuples(index=False)])
        st_csv = os.path.join(RAW_DIR, "stocktakes.csv")
        if os.path.exists(st_csv):
            stc = pd.read_csv(st_csv, encoding="utf-8-sig").fillna({"note": "", "created_by": ""})
            conn.executemany(
                "INSERT INTO stocktakes(date, product_id, book_qty, counted_qty, note, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(r.date, prod_ids[r.product], float(r.book_qty), float(r.counted_qty), r.note,
                  r.created_by) for r in stc.itertuples(index=False)])


# ---------------------------------------------------------------------------
# Đọc dữ liệu (trả về pandas DataFrame)
# ---------------------------------------------------------------------------
def categories_df(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT c.id, c.name, c.description, c.manager_id, "
        "COALESCE(NULLIF(u.full_name, ''), u.username) AS manager, COUNT(p.id) AS products "
        "FROM categories c LEFT JOIN products p ON p.category_id = c.id "
        "LEFT JOIN users u ON u.id = c.manager_id "
        "GROUP BY c.id ORDER BY c.name", conn)


def set_category_manager(conn: sqlite3.Connection, category_id: int, user_id: int | None) -> None:
    """Giao (hoặc bỏ giao, user_id=None) một danh mục cho người quản lý."""
    with conn:
        conn.execute("UPDATE categories SET manager_id = ? WHERE id = ?", (user_id, category_id))


def assign_from_config(conn: sqlite3.Connection, mapping) -> None:
    """Phân công từ secrets: {"tên tài khoản": ["Danh mục 1", ...]} (chỉ gán danh mục chưa có người)."""
    for username, cat_names in dict(mapping or {}).items():
        u = conn.execute("SELECT id FROM users WHERE username = ?",
                         (" ".join(str(username).split()).lower(),)).fetchone()
        if u is None:
            continue
        for name in cat_names:
            conn.execute("UPDATE categories SET manager_id = ? WHERE name = ? AND manager_id IS NULL",
                         (u["id"], name))
    conn.commit()


def products_df(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT p.id, p.name, p.category_id, c.name AS category, p.unit, p.price, "
        "p.min_stock, p.shelf_life_days, p.storage_zone, p.storage_note, p.note, c.manager_id FROM products p "
        "LEFT JOIN categories c ON c.id = p.category_id ORDER BY c.name, p.name", conn)


def transactions_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT t.id, t.date, t.product_id, p.name AS product, c.name AS category, "
        "p.unit, t.type, t.quantity, t.unit_price, t.note, t.created_by FROM transactions t "
        "JOIN products p ON p.id = t.product_id "
        "LEFT JOIN categories c ON c.id = p.category_id "
        "ORDER BY t.date DESC, t.id DESC", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def current_stock(conn: sqlite3.Connection, product_id: int) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN type IN ('in', 'adj_plus') THEN quantity ELSE -quantity END), 0) "
        "FROM transactions WHERE product_id = ?", (product_id,)).fetchone()
    return round(float(row[0]), 3)


# ---------------------------------------------------------------------------
# Ghi dữ liệu (ném ValueError kèm thông báo tiếng Việt khi dữ liệu sai)
# ---------------------------------------------------------------------------
def _check_shelf(shelf_life_days: float) -> int:
    if not shelf_life_days or shelf_life_days < 1:
        raise ValueError("Hạn sử dụng phải từ 1 ngày trở lên.")
    return int(shelf_life_days)


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
                opening_qty: float = 0, date: dt.date | None = None,
                shelf_life_days: int = 365, storage_zone: str = "", storage_note: str = "") -> int:
    """Thêm sản phẩm; nếu opening_qty > 0 thì ghi luôn một phiếu nhập tồn đầu."""
    _check_product(name, unit, price, min_stock)
    shelf = _check_shelf(shelf_life_days)
    if opening_qty < 0:
        raise ValueError("Số lượng tồn đầu phải ≥ 0.")
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO products(name, category_id, unit, price, min_stock, shelf_life_days,"
                " storage_zone, storage_note, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), category_id, unit, price, min_stock, shelf, storage_zone or "",
                 (storage_note or "").strip(), note.strip()))
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
                   min_stock: float, note: str = "", shelf_life_days: int = 365,
                   storage_zone: str = "", storage_note: str = "") -> None:
    _check_product(name, unit, price, min_stock)
    shelf = _check_shelf(shelf_life_days)
    try:
        with conn:
            conn.execute(
                "UPDATE products SET name=?, category_id=?, unit=?, price=?, min_stock=?,"
                " shelf_life_days=?, storage_zone=?, storage_note=?, note=? WHERE id=?",
                (name.strip(), category_id, unit, price, min_stock, shelf, storage_zone or "",
                 (storage_note or "").strip(), note.strip(), product_id))
    except sqlite3.IntegrityError:
        raise ValueError(f"Sản phẩm “{name}” đã tồn tại.") from None


def delete_product(conn: sqlite3.Connection, product_id: int) -> None:
    """Xóa sản phẩm và toàn bộ lịch sử giao dịch của nó."""
    with conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def stocktakes_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT s.id, s.date, s.product_id, p.name AS product, c.name AS category, p.unit, p.price, "
        "s.book_qty, s.counted_qty, s.counted_qty - s.book_qty AS diff, s.note, s.created_by "
        "FROM stocktakes s JOIN products p ON p.id = s.product_id "
        "LEFT JOIN categories c ON c.id = p.category_id ORDER BY s.date DESC, s.id DESC", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def add_stocktake(conn: sqlite3.Connection, product_id: int, counted_qty: float,
                  date: dt.date | None = None, note: str = "", created_by: str = "") -> float:
    """Ghi phiếu kiểm kê; nếu lệch sổ thì tự lập phiếu điều chỉnh cho tồn kho khớp thực tế.

    Trả về số chênh lệch (thực tế − sổ sách).
    """
    if counted_qty is None or counted_qty < 0:
        raise ValueError("Số lượng đếm thực tế phải ≥ 0.")
    book = current_stock(conn, product_id)
    diff = round(counted_qty - book, 3)
    d = (date or dt.date.today()).isoformat()
    price = conn.execute("SELECT price FROM products WHERE id = ?", (product_id,)).fetchone()
    if price is None:
        raise ValueError("Sản phẩm không tồn tại.")
    with conn:
        conn.execute("INSERT INTO stocktakes(date, product_id, book_qty, counted_qty, note, created_by)"
                     " VALUES (?, ?, ?, ?, ?, ?)", (d, product_id, book, counted_qty, note.strip(), created_by))
        if abs(diff) > 1e-9:
            conn.execute(
                "INSERT INTO transactions(date, product_id, type, quantity, unit_price, note, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (d, product_id, TX_ADJ_PLUS if diff > 0 else TX_ADJ_MINUS, abs(diff), float(price[0]),
                 "Chênh lệch kiểm kê", created_by))
    return diff


def add_transaction(conn: sqlite3.Connection, product_id: int, tx_type: str,
                    quantity: float, unit_price: float,
                    date: dt.date | None = None, note: str = "", created_by: str = "") -> None:
    """Ghi một phiếu nhập / xuất / hủy hàng. Không cho xuất hoặc hủy vượt quá tồn kho."""
    if tx_type not in (TX_IN, TX_OUT, TX_DISPOSE):
        raise ValueError("Loại giao dịch không hợp lệ.")
    if quantity <= 0:
        raise ValueError("Số lượng phải lớn hơn 0.")
    if unit_price < 0:
        raise ValueError("Đơn giá phải ≥ 0.")
    if tx_type in (TX_OUT, TX_DISPOSE):
        stock = current_stock(conn, product_id)
        if quantity > stock:
            verb = "xuất" if tx_type == TX_OUT else "hủy"
            raise ValueError(f"Không đủ hàng để {verb}: chỉ còn {catalog.fmt_qty(stock)}.")
    with conn:
        conn.execute(
            "INSERT INTO transactions(date, product_id, type, quantity, unit_price, note, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ((date or dt.date.today()).isoformat(), product_id, tx_type,
             quantity, unit_price, note.strip(), created_by))
