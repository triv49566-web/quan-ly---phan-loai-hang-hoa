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
├── app.py                        # Ứng dụng Streamlit (giao diện, 9 trang)
├── requirements.txt              # Thư viện cần cài
├── README.md                     # Tài liệu này
├── .streamlit/
│   └── config.toml               # Giao diện / theme / tắt usage stats
├── data/
│   ├── generate_sample_data.py   # Script sinh dữ liệu mẫu (seed cố định → tái lập)
│   ├── hanghoa.db                # CSDL SQLite (tự tạo khi chạy lần đầu, không đưa lên git)
│   └── raw/
│       ├── products.csv          # 18 sản phẩm mẫu (có hạn sử dụng)
│       └── transactions.csv      # Lịch sử nhập / xuất / hủy năm 2026
└── src/
    ├── __init__.py
    ├── auth.py                   # Tài khoản đăng nhập, băm mật khẩu
    ├── catalog.py                # Danh mục mặc định, đơn vị tính, quy tắc trạng thái tồn kho
    ├── database.py               # Lưu trữ SQLite: tạo bảng, đọc / ghi, kiểm tra dữ liệu
    ├── inventory.py              # Tồn kho, tồn theo ngày, lô hàng & hạn dùng, báo cáo cuối ngày
    ├── kpi.py                    # KPI quy trình quản lý kho: tiêu chí, chỉ số, tiêu chuẩn, cải tiến
    └── risk.py                   # Quản lý rủi ro: nhận diện, đánh giá, biện pháp
```

**Vai trò từng lớp** (tách bạch dữ liệu – logic – giao diện):

| Lớp | File | Nhiệm vụ |
|-----|------|----------|
| Dữ liệu | `data/`, `src/database.py` | Sinh dữ liệu mẫu, lưu trữ SQLite |
| Logic | `src/catalog.py`, `src/inventory.py`, `src/kpi.py`, `src/risk.py` | Phân loại, tồn kho, KPI, rủi ro |
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

**Các trang (chọn ở thanh bên, chia 3 nhóm):**

| Nhóm | Trang | Công dụng |
|------|-------|-----------|
| Kho hàng | **Tồn kho** | Ô tổng quan, khối *Cần nhập hàng*, bảng tồn kho; lọc theo danh mục và **nhóm bảo quản** (*Để lâu được* / *Mau hỏng*), hạn dùng và lô gần hết hạn |
| | **Nhập / Xuất kho** | Ghi phiếu **nhập**, **xuất** hoặc **hủy hàng** (hết hạn / hư hỏng); không cho xuất / hủy quá tồn kho |
| | **Sản phẩm & danh mục** | Thêm / sửa / xóa sản phẩm (có **hạn sử dụng**, **mức dự trữ**); thêm / xóa danh mục |
| | **Lịch sử giao dịch** | Lọc theo tên, loại, danh mục, khoảng ngày; tải CSV |
| Báo cáo & đánh giá | **Báo cáo cuối ngày** | Chọn ngày: tồn đầu ngày, nhập, xuất, hủy, tồn cuối ngày, hàng cận hạn, hàng dưới mức dự trữ; tải CSV |
| | **Đánh giá KPI theo quý** | Điểm tổng hợp & **xếp loại người phụ trách kho**, bảng *Tiêu chí – Chỉ số – Tiêu chuẩn*, so sánh với quý trước (cải thiện / xấu đi), biểu đồ xu hướng, **phương án cải tiến**; tải CSV |
| | **Báo cáo** | Biểu đồ: giá trị tồn theo danh mục, trạng thái, nhập / xuất / hủy **theo tháng hoặc theo quý**, top hàng xuất nhiều, tồn theo nhóm bảo quản, hàng hủy theo quý |
| | **Quản lý rủi ro** | Danh sách rủi ro (hết hàng, dưới dự trữ, cận hạn, quá hạn, tồn đọng), **ma trận rủi ro** khả năng × ảnh hưởng, biện pháp xử lý; tải CSV |
| Hệ thống | **Tài khoản** | Đổi mật khẩu; quản trị viên quản lý tài khoản |

**Đăng nhập:**
- Mọi trang đều cần đăng nhập bằng *tài khoản* và *mật khẩu*.
- Lần đầu mở app (chưa có tài khoản nào) sẽ hiện màn hình **Tạo tài khoản quản trị**.
  Hoặc đặt sẵn tài khoản quản trị trong `.streamlit/secrets.toml` (xem
  `.streamlit/secrets.toml.example`); trên Streamlit Cloud dán vào *Settings → Secrets*.
- Trang **Tài khoản**: ai cũng đổi được mật khẩu của mình; quản trị viên thêm / xóa
  tài khoản và đặt lại mật khẩu cho người khác.
- Hai loại tài khoản:

  | Loại | Thấy các trang |
  |------|----------------|
  | **Quản trị viên** | Tất cả các trang |
  | **Nhân viên (chỉ xem)** | Tồn kho, Lịch sử giao dịch, 4 trang báo cáo & đánh giá, Tài khoản (đổi mật khẩu). Không ghi phiếu, không sửa sản phẩm / danh mục |

  Khi thêm tài khoản, bỏ trống ô *Quản trị viên* là tạo tài khoản nhân viên.
- Mật khẩu được băm (PBKDF2-SHA256, có salt), không lưu dạng chữ thường.
  Nhập sai 5 lần liên tiếp phải chờ 60 giây.
- Tải lại trang (F5) sẽ phải đăng nhập lại.

**Ý nghĩa màu trạng thái:** 🟢 Đủ hàng · 🟠 Sắp hết (≤ mức tồn tối thiểu) · 🔴 Hết hàng.

---

## 4. Bộ dữ liệu mẫu

6 danh mục: *Sữa & đồ uống, Lương thực, Gia vị, Dầu ăn, Đồ khô, Thực phẩm tươi*.
Mô phỏng từ **01/01/2026 đến 12/11/2026 (4 quý)**:
- mỗi ngày xuất bán ngẫu nhiên quanh mức tiêu thụ bình quân (Tết tháng 1–2 bán chạy hơn);
- hàng nhập theo lô, xuất theo **nhập trước – xuất trước**; lô quá hạn bị **hủy**;
- quy trình được **cải tiến dần qua từng quý** (nhập kịp thời hơn, lô hàng mau hỏng nhỏ lại)
  nên KPI tăng từ loại B (quý 1) lên loại A (quý 3) và hàng hủy giảm rõ;
- vài mặt hàng ngừng nhập cuối kỳ để có ví dụ *Sắp hết / Hết hàng*.

**`products.csv`**

| Cột | Ý nghĩa |
|-----|---------|
| `name` | Tên sản phẩm |
| `category` | Danh mục |
| `unit` | Đơn vị tính (kg, g, lít, ml, gói, chai, hộp, ...) |
| `price` | Đơn giá tham khảo (đ / đơn vị) |
| `min_stock` | Mức tồn tối thiểu = lượng dự trữ phải giữ (để cảnh báo) |
| `shelf_life_days` | Hạn sử dụng (ngày, tính từ ngày nhập). ≥ 90 ngày: *Để lâu được*; ngắn hơn: *Mau hỏng* |
| `note` | Ghi chú |

**`transactions.csv`**

| Cột | Ý nghĩa |
|-----|---------|
| `date` | Ngày (YYYY-MM-DD) |
| `product` | Tên sản phẩm (khớp `products.csv`) |
| `type` | `in` = nhập kho, `out` = xuất kho, `dispose` = hủy hàng (hết hạn / hư hỏng) |
| `quantity` | Số lượng (theo đơn vị của sản phẩm) |
| `unit_price` | Đơn giá của giao dịch |
| `note` | Ghi chú |

---

## 5. Các chỉ số & công thức

| Chỉ số | Công thức |
|--------|-----------|
| Tồn kho | Tổng nhập − Tổng xuất − Tổng hủy |
| Giá trị tồn | Tồn kho × Đơn giá |
| Xuất 30 ngày | Tổng xuất trong 30 ngày tính đến giao dịch gần nhất |
| Đủ dùng (ngày) | Tồn kho ÷ (Xuất 30 ngày ÷ 30) |
| Trạng thái | Hết hàng nếu tồn ≤ 0 · Sắp hết nếu tồn ≤ mức tối thiểu · còn lại Đủ hàng |

| Cận hạn | Lô hàng còn ≤ 20% hạn dùng (tối thiểu 2, tối đa 30 ngày) |

Chi tiết trong [`src/inventory.py`](src/inventory.py) và [`src/catalog.py`](src/catalog.py).

### KPI đánh giá quy trình quản lý kho (theo quý)

**1. Đối tượng:** quy trình quản lý kho nhu yếu phẩm (qua đó đánh giá người phụ trách kho).
**2. Tiêu chí → Chỉ số → Tiêu chuẩn:**

| Tiêu chí | Chỉ số | Công thức | Tiêu chuẩn (Đạt · Cảnh báo) | Trọng số |
|----------|--------|-----------|-----------------------------|----------|
| Bảo đảm dự trữ | Tỷ lệ ngày còn hàng | (ngày × mặt hàng) tồn > 0 ÷ tổng | ≥ 98% · ≥ 95% | 20% |
| | Tỷ lệ đạt mức dự trữ | (ngày × mặt hàng) tồn > mức tối thiểu ÷ tổng | ≥ 90% · ≥ 80% | 15% |
| | Số lần hết hàng | số lần chuyển từ còn hàng sang hết hàng | ≤ 2 · ≤ 5 | 10% |
| Chất lượng bảo quản | Tỷ lệ hao hụt do hết hạn | giá trị hủy ÷ giá trị nhập | ≤ 1% · ≤ 3% | 15% |
| | Tỷ lệ hàng cận hạn cuối quý | giá trị lô cận hạn ÷ giá trị tồn | ≤ 5% · ≤ 10% | 10% |
| Hiệu suất sử dụng vốn | Vòng quay tồn kho (quy năm) | giá trị xuất ÷ tồn bình quân × 365 ÷ số ngày | ≥ 24 · ≥ 15 | 10% |
| | Tỷ lệ hàng tồn đọng | giá trị hàng cần > 60 ngày mới bán hết ÷ giá trị tồn | ≤ 10% · ≤ 20% | 10% |
| Tuân thủ quy trình | Tỷ lệ nhập hàng kịp thời | lần chạm mức dự trữ có phiếu nhập trong ≤ 2 ngày ÷ tổng | ≥ 90% · ≥ 75% | 10% |

**3. Dữ liệu:** phiếu nhập / xuất / hủy và danh mục sản phẩm (đơn giá, mức dự trữ, hạn dùng).

**Điểm tổng hợp** = Σ trọng số × hệ số (Đạt 100% · Cảnh báo 60% · Chưa đạt 20%).
**Xếp loại:** A ≥ 85 (Tốt) · B ≥ 70 (Khá) · C ≥ 50 (Trung bình) · D < 50 (Cần cải thiện).
Đổi tiêu chuẩn / trọng số / biện pháp cải tiến → sửa `KPI_DEFS` và `ACTIONS` trong [`src/kpi.py`](src/kpi.py).

### Quản lý rủi ro

Mức rủi ro = **khả năng xảy ra (1–5) × mức ảnh hưởng (1–5)**: ≥ 15 *Cao* (xử lý trong ngày),
8–14 *Trung bình* (trong tuần), < 8 *Thấp* (theo dõi). Loại rủi ro và biện pháp nằm trong
[`src/risk.py`](src/risk.py).

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
