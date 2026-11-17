# 🛒 Quản lý & phân loại nhu yếu phẩm (Streamlit)

Ứng dụng web viết bằng **Python + Streamlit** để **quản lý tồn kho, nhập / xuất
hàng và phân loại** các mặt hàng thiết yếu hằng ngày: sữa (lít), gạo (kg),
muối, tiêu, dầu ăn, bột ngọt...

Có sẵn bộ dữ liệu mẫu (16 mặt hàng, ~1.400 giao dịch trong 3,5 tháng) để chạy
thử ngay.

---

## Mục lục
1. [Cấu trúc thư mục](#1-cấu-trúc-thư-mục)
2. [Cài đặt & chạy](#2-cài-đặt--chạy)
3. [Hướng dẫn sử dụng giao diện](#3-hướng-dẫn-sử-dụng-giao-diện)
4. [Bộ dữ liệu mẫu](#4-bộ-dữ-liệu-mẫu)
5. [Các chỉ số & công thức](#5-các-chỉ-số--công-thức)
6. [Tùy chỉnh nhanh](#6-tùy-chỉnh-nhanh)
7. [Hướng phát triển](#7-hướng-phát-triển)
8. [Xử lý sự cố thường gặp](#8-xử-lý-sự-cố-thường-gặp)

---

## 1. Cấu trúc thư mục

```
quan_ly_hang_hoa/
├── app.py                        # Ứng dụng Streamlit (giao diện chính, 5 tab)
├── requirements.txt              # Thư viện cần cài
├── README.md                     # Tài liệu này
├── .streamlit/
│   └── config.toml               # Giao diện / theme / tắt usage stats
├── data/
│   ├── generate_sample_data.py   # Script sinh dữ liệu mẫu (seed cố định → tái lập)
│   ├── hanghoa.db                # CSDL SQLite (tự tạo khi chạy lần đầu, không đưa lên git)
│   └── raw/
│       ├── products.csv          # 16 sản phẩm mẫu
│       └── transactions.csv      # Lịch sử nhập / xuất mẫu
└── src/
    ├── __init__.py
    ├── auth.py                   # Tài khoản đăng nhập, băm mật khẩu
    ├── catalog.py                # Danh mục mặc định, đơn vị tính, quy tắc trạng thái tồn kho
    ├── database.py               # Lưu trữ SQLite: tạo bảng, đọc / ghi, kiểm tra dữ liệu
    └── inventory.py              # Tính tồn kho, giá trị, số ngày đủ dùng, báo cáo
```

**Vai trò từng lớp** (tách bạch dữ liệu – logic – giao diện):

| Lớp | File | Nhiệm vụ |
|-----|------|----------|
| Dữ liệu | `data/`, `src/database.py` | Sinh dữ liệu mẫu, lưu trữ SQLite |
| Logic | `src/catalog.py`, `src/inventory.py` | Quy tắc phân loại, tính tồn kho & báo cáo |
| Giao diện | `app.py` | Hiển thị, lọc, nhập liệu, vẽ biểu đồ |

> Nhờ tách lớp, bạn có thể dùng lại `src/` trong notebook, script khác hoặc
> làm API (Flask / FastAPI) mà không cần Streamlit.

---

## 2. Cài đặt & chạy

Yêu cầu: **Python 3.9+**.

```bash
# 1) Vào thư mục dự án
cd quan_ly_hang_hoa

# 2) (Khuyến nghị) tạo môi trường ảo
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Cài thư viện
pip install -r requirements.txt

# 4) (Tùy chọn) sinh lại dữ liệu mẫu
python data/generate_sample_data.py

# 5) Chạy ứng dụng
streamlit run app.py
```

Mở trình duyệt tại `http://localhost:8501`. Dừng app bằng **Ctrl + C**.

> ⚠️ Hãy chạy lệnh `streamlit run` **từ bên trong thư mục dự án** để app đọc
> đúng file `.streamlit/config.toml`.

Lần chạy đầu, app tự tạo `data/hanghoa.db` và nạp dữ liệu từ `data/raw/*.csv`.
Mọi thao tác thêm / sửa / nhập / xuất sau đó được lưu vào file này.

---

## 3. Hướng dẫn sử dụng giao diện

Giao diện **“Sổ Kho”**: thanh điều hướng xanh đậm bên trái, nền xám nhạt, các
khối nội dung màu trắng, chữ *Be Vietnam Pro*. Màu và font nằm trong
`.streamlit/config.toml`, phần trang trí thêm nằm ở biến `CSS` trong `app.py`.

**5 trang (chọn ở thanh bên):**

| Trang | Công dụng |
|-------|-----------|
| **Tồn kho** | 4 ô tổng quan, khối *Cần nhập hàng*, bảng tồn kho có thanh so với mức tối thiểu; tìm theo tên, lọc theo danh mục; tải CSV |
| **Nhập / Xuất kho** | Ghi phiếu nhập hoặc xuất, xem trước *tồn sau phiếu* và *thành tiền* (không cho xuất quá tồn kho); 12 giao dịch gần nhất |
| **Sản phẩm & danh mục** | Thêm / sửa / xóa sản phẩm; thêm / xóa danh mục |
| **Báo cáo** | Giá trị tồn theo danh mục, trạng thái theo danh mục, nhập/xuất theo tháng, top hàng xuất nhiều |
| **Lịch sử giao dịch** | Lọc theo tên, loại, danh mục, khoảng ngày; tải CSV |

**Đăng nhập:**
- Mọi trang đều cần đăng nhập bằng *tài khoản* và *mật khẩu*.
- Lần đầu mở app (chưa có tài khoản nào) sẽ hiện màn hình **Tạo tài khoản quản trị**.
  Hoặc đặt sẵn tài khoản quản trị trong `.streamlit/secrets.toml` (xem
  `.streamlit/secrets.toml.example`); trên Streamlit Cloud dán vào *Settings → Secrets*.
- Trang **Tài khoản**: ai cũng đổi được mật khẩu của mình; quản trị viên thêm / xóa
  tài khoản và đặt lại mật khẩu cho người khác.
- Mật khẩu được băm (PBKDF2-SHA256, có salt), không lưu dạng chữ thường.
  Nhập sai 5 lần liên tiếp phải chờ 60 giây.
- Tải lại trang (F5) sẽ phải đăng nhập lại.

**Ý nghĩa màu trạng thái:** 🟢 Đủ hàng · 🟠 Sắp hết (≤ mức tồn tối thiểu) · 🔴 Hết hàng.

---

## 4. Bộ dữ liệu mẫu

5 danh mục: *Sữa & đồ uống, Lương thực, Gia vị, Dầu ăn, Đồ khô*.
Mô phỏng từ 01/08/2026 đến 12/11/2026: mỗi ngày xuất bán ngẫu nhiên quanh mức
tiêu thụ bình quân, tồn thấp thì nhập lô mới. Một vài mặt hàng ngừng nhập cuối
kỳ để có ví dụ *Sắp hết / Hết hàng*.

**`products.csv`**

| Cột | Ý nghĩa |
|-----|---------|
| `name` | Tên sản phẩm |
| `category` | Danh mục |
| `unit` | Đơn vị tính (kg, g, lít, ml, gói, chai, hộp, ...) |
| `price` | Đơn giá tham khảo (đ / đơn vị) |
| `min_stock` | Mức tồn tối thiểu (để cảnh báo) |
| `note` | Ghi chú |

**`transactions.csv`**

| Cột | Ý nghĩa |
|-----|---------|
| `date` | Ngày (YYYY-MM-DD) |
| `product` | Tên sản phẩm (khớp `products.csv`) |
| `type` | `in` = nhập kho, `out` = xuất kho |
| `quantity` | Số lượng (theo đơn vị của sản phẩm) |
| `unit_price` | Đơn giá của giao dịch |
| `note` | Ghi chú |

---

## 5. Các chỉ số & công thức

| Chỉ số | Công thức |
|--------|-----------|
| Tồn kho | Tổng nhập − Tổng xuất |
| Giá trị tồn | Tồn kho × Đơn giá |
| Xuất 30 ngày | Tổng xuất trong 30 ngày tính đến giao dịch gần nhất |
| Đủ dùng (ngày) | Tồn kho ÷ (Xuất 30 ngày ÷ 30) |
| Trạng thái | Hết hàng nếu tồn ≤ 0 · Sắp hết nếu tồn ≤ mức tối thiểu · còn lại Đủ hàng |

Chi tiết trong [`src/inventory.py`](src/inventory.py) và [`src/catalog.py`](src/catalog.py).

> **Lưu ý:** tồn kho **không lưu cố định** mà luôn tính lại từ lịch sử giao dịch,
> nên số liệu luôn khớp với sổ nhập / xuất.

---

## 6. Tùy chỉnh nhanh

**Thêm đơn vị tính** → sửa danh sách `UNITS` trong [`src/catalog.py`](src/catalog.py).

**Đổi danh mục mặc định** → sửa `DEFAULT_CATEGORIES` trong `src/catalog.py`
(chỉ áp dụng khi tạo CSDL mới), hoặc thêm trực tiếp ở tab *Sản phẩm & Danh mục*.

**Đổi quy tắc cảnh báo** → sửa hàm `evaluate_stock()` trong `src/catalog.py`;
đổi số ngày tính tiêu thụ → `WINDOW_DAYS` trong `src/inventory.py`.

**Dùng dữ liệu thật** → thay `data/raw/products.csv` và `transactions.csv`
(giữ đúng tên cột), xóa `data/hanghoa.db` rồi chạy lại app.

**Làm lại từ đầu** → xóa `data/hanghoa.db`.

**Đổi giao diện / màu** → sửa `.streamlit/config.toml` và `PALETTE`,
`STATUS_COLOR` trong `app.py` / `src/catalog.py`.

---

## 7. Hướng phát triển

**Mức cơ bản**
- [ ] Quản lý **hạn sử dụng** theo lô hàng, cảnh báo hàng sắp hết hạn.
- [ ] Thêm **nhà cung cấp** cho phiếu nhập.
- [ ] Xuất **báo cáo Excel / PDF** (`openpyxl` / `reportlab`).
- [ ] Quét **mã vạch** sản phẩm.

**Mức trung bình**
- [ ] **Đăng nhập & phân quyền** (thủ kho / quản lý) bằng `streamlit-authenticator`.
- [ ] Tách **giá nhập** và **giá bán**, tính lợi nhuận gộp.
- [ ] **Cảnh báo tự động** qua email / Zalo khi hàng sắp hết.
- [ ] Chuyển sang **PostgreSQL** với `SQLAlchemy` khi nhiều người dùng.

**Mức nâng cao**
- [ ] **Dự báo nhu cầu** và gợi ý số lượng đặt hàng (hồi quy / Prophet).
- [ ] Phân tích **ABC** hàng tồn kho.
- [ ] Làm **REST API** (FastAPI) dùng lại `src/` cho app di động.
- [ ] **Triển khai online**: Streamlit Community Cloud, Docker.

---

## 8. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|------------|--------------------------|
| `ModuleNotFoundError: streamlit` | Chưa cài thư viện → `pip install -r requirements.txt` |
| Dữ liệu mẫu mới không hiện ra | App chỉ nạp CSV khi CSDL trống → xóa `data/hanghoa.db` rồi chạy lại |
| `database is locked` | Đang mở `hanghoa.db` bằng phần mềm khác → đóng phần mềm đó |
| Dòng *"Collecting usage statistics..."* | **Không phải lỗi**, đã tắt sẵn trong `.streamlit/config.toml` |
| Cổng 8501 bị chiếm | `streamlit run app.py --server.port 8600` |

---

*Dự án mẫu phục vụ học tập. Mọi số liệu là giả định.*
