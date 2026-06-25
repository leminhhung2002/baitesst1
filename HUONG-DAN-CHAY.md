# Hướng dẫn chạy — KOC Data System

Hệ thống gồm 2 phần: **backend** (FastAPI, Python) và **frontend** (React + Vite).
Có 2 cách chạy: **Docker** (nhanh nhất) hoặc **chạy local** (không cần Docker, dùng SQLite).

---

## 0. Yêu cầu môi trường

| Công cụ | Phiên bản | Bắt buộc khi |
|---|---|---|
| Python | 3.11+ (đã test 3.13) | Chạy backend local |
| Node.js | 18+ (đã test 22) | Chạy frontend |
| Docker + Docker Compose | mới | Chạy bằng Docker |
| PostgreSQL | 14+ | (Tuỳ chọn) chạy local với Postgres thay vì SQLite |

> Mặc định khi chạy local, backend dùng **SQLite** (1 file `koc.db`) nên **không cần cài Postgres**.

---

## Cách 1 — Chạy bằng Docker (khuyên dùng)

Từ thư mục `koc-system/`:

```bash
docker compose up --build
```

- Backend chạy ở `http://localhost:8000` (tài liệu API: `http://localhost:8000/docs`).
- Lần đầu khởi động, hệ thống **tự seed ~103 KOC** từ nguồn mặc định.

Sau đó mở **terminal thứ 2** để chạy frontend:

```bash
cd frontend
npm install
npm run dev
```

Mở trình duyệt: **http://localhost:5173**

---

## Cách 2 — Chạy local (không Docker, dùng SQLite)

### 2.1. Backend

Từ thư mục `koc-system/backend/`:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # tạo file cấu hình
uvicorn app.main:app --reload   # tự tạo bảng + seed lần đầu
```

**macOS / Linux (bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Backend chạy ở `http://localhost:8000`. Lần đầu sẽ tự tạo bảng và seed dữ liệu (mất ~1 phút vì lấy follower live).

### 2.2. Frontend

Mở **terminal khác**, từ thư mục `koc-system/frontend/`:

```bash
npm install
npm run dev
```

Mở trình duyệt: **http://localhost:5173** (Vite đã proxy `/api` về backend `:8000`).

---

## 3. Cấu hình (file `backend/.env`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./koc.db` | Kết nối CSDL. Dùng Postgres: `postgresql+psycopg2://user:pass@host:5432/db` |
| `DATA_SOURCE` | `tiktok_top` | Nguồn dữ liệu (xem mục 5) |
| `MIN_FOLLOWER` | `500000` | Ngưỡng lọc follower khi đồng bộ |
| `AUTO_SYNC_ENABLED` | `true` | Bật đồng bộ tự động theo lịch |
| `SYNC_INTERVAL_MINUTES` | `60` | Chu kỳ đồng bộ tự động (phút) |
| `SEED_ON_STARTUP` | `true` | Tự seed dữ liệu khi DB trống lúc khởi động |
| `UNAVATAR_KEY` | *(trống)* | (Tuỳ chọn) key unavatar dự phòng cho avatar |
| `CORS_ORIGINS` | `http://localhost:5173` | Domain frontend được phép gọi API |

> Sửa `.env` xong cần **khởi động lại backend** để áp dụng.

---

## 4. Sử dụng

- **Xem dữ liệu:** mở `http://localhost:5173` — dashboard + danh sách KOC.
- **Tìm kiếm / lọc / sắp xếp:** dùng ô tìm kiếm, ô lọc follower/doanh thu, bấm tiêu đề cột để sắp xếp.
- **Xem chi tiết:** bấm vào một dòng KOC → modal chi tiết + biểu đồ tăng trưởng.
- **Đồng bộ thủ công:** bấm nút **"Đồng bộ ngay"** (chạy nền ~1 phút, giao diện tự cập nhật).
- **Đồng bộ tự động:** chạy nền theo `SYNC_INTERVAL_MINUTES`. Mỗi lần follower thay đổi sẽ ghi thêm điểm cho biểu đồ.
- **Lịch sử đồng bộ:** bấm **"Lịch sử đồng bộ"** trên dashboard.
- **Tài liệu API (Swagger):** `http://localhost:8000/docs`.

---

## 5. Nguồn dữ liệu (đổi qua `DATA_SOURCE`)

| Giá trị | Mô tả |
|---|---|
| `tiktok_top` *(mặc định)* | ~103 KOC cá nhân VN, follower **live** qua API công khai tikwm + avatar thật |
| `tiktok_oembed` | Danh tính live qua TikTok oEmbed + follower từ danh sách tuyển chọn |
| `real` | Provider trả phí (FastMoss/Kalodata…) — điền `REAL_API_*` rồi sửa `app/sources/real.py` |
| `mock` | Dữ liệu giả lập (offline) |

> **Avatar** được tải 1 lần và cache vào `backend/avatars/`, phục vụ qua `/api/avatar/<handle>`.
> Không lấy được ảnh → giao diện tự hiển thị avatar chữ cái.

---

## 6. Chạy kiểm thử (test)

Từ thư mục `koc-system/backend/` (test dùng SQLite trong bộ nhớ, **không cần Postgres**):

```bash
pip install -r requirements-dev.txt
pytest
```

Kết quả mong đợi: **11 passed**.

---

## 7. Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Sửa code backend nhưng không thấy đổi | Khởi động lại uvicorn (hoặc chạy với cờ `--reload`) |
| Cổng `8000`/`5173` đang bận | Tắt tiến trình cũ, hoặc đổi cổng (`uvicorn ... --port 8001`, `npm run dev -- --port 5174`) |
| Avatar không hiện (chữ cái) | Quota nguồn ảnh tạm hết — sẽ tự tải lại sau, hoặc đặt `UNAVATAR_KEY` rồi đồng bộ lại |
| Frontend gọi API lỗi CORS | Kiểm tra `CORS_ORIGINS` trong `.env` khớp domain frontend |
| Đồng bộ chậm (~1 phút) | Bình thường — nguồn live có giới hạn tần suất nên phải throttle; sync chạy nền nên không chặn UI |
| Muốn nạp lại dữ liệu từ đầu | Xoá `backend/koc.db` (SQLite) rồi khởi động lại backend để seed lại |

---

## 8. Lệnh nhanh (tóm tắt)

```bash
# Backend (local, SQLite)
cd backend && python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt && copy .env.example .env
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Test
cd backend && pytest

# Docker (tất cả backend + DB)
docker compose up --build
```

Truy cập: **Giao diện** http://localhost:5173 · **API docs** http://localhost:8000/docs
