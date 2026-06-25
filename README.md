# KOC Data System — Demo

Hệ thống dữ liệu KOC tập trung: thu thập → lưu kho riêng → tìm kiếm/lọc →
đồng bộ (thủ công + theo lịch) → giao diện quản trị.

> **Sự thật đã kiểm chứng (gọi API thật 2026-06):** TikTok oEmbed CHỈ trả về
> tên hiển thị + link kênh + xác nhận hồ sơ tồn tại — **KHÔNG có follower,
> doanh thu, avatar**. Tải trang profile để bóc `followerCount` thì bị TikTok
> chặn bot (SlardarWAF). **Không có nguồn miễn phí nào** trả follower/doanh thu
> KOC. Vì vậy hệ thống dùng cách trung thực: danh tính lấy LIVE & thật từ
> oEmbed, **follower lấy từ bảng tuyển chọn `CURATED_KOCS`** (số công khai, xấp
> xỉ, cập nhật tay), doanh thu là **ước lượng** (đánh dấu rõ trong `raw_json`).

## Nguồn dữ liệu (đổi qua `DATA_SOURCE`)

| `DATA_SOURCE` | Dữ liệu | Cần key? | Dùng khi |
|---|---|---|---|
| `tiktok_top` *(mặc định)* | **~90 KOC VN THẬT** lấy từ bảng xếp hạng follower công khai (HypeAuditor/hafi.pro): tên + **follower thật** + **avatar thật** (đã tải sẵn về `backend/avatars/`, phục vụ qua `/api/avatar/<handle>`). Xếp theo follower nên **không thể lọt nick giả mạo**. Doanh thu **ước lượng** (`raw_json.estimated_revenue=true`). | **Không** | Demo mặc định — nhiều KOC thật + có ảnh đại diện |
| `tiktok_oembed` | Danh tính live qua oEmbed + follower từ bảng tuyển chọn ~36 KOC. Avatar phụ thuộc unavatar (dễ bị 429). | **Không** | Khi muốn xác minh hồ sơ live qua oEmbed |
| `real` | Provider bên thứ ba (FastMoss/Kalodata…) — follower + doanh thu thật, live | Có | Khi có tài khoản provider; sửa `app/sources/real.py` |

> Dữ liệu `tiktok_top` nằm ở `app/data/koc_top_vn.json` (sinh từ
> `app/data/raw_top_vn.txt`). Cập nhật danh sách mới: chụp lại bảng xếp hạng vào
> file raw rồi chạy script build để tải avatar + ghi JSON.
> `mock` đã **bỏ** khỏi luồng mặc định (file vẫn còn để tham khảo).

Tùy biến danh sách & ngưỡng lọc (`.env`):
```bash
DATA_SOURCE=tiktok_oembed
MIN_FOLLOWER=500000                       # loại KOC dưới ngưỡng
TIKTOK_HANDLES=giadinhcamcam,phamthoai    # tuỳ chọn; handle phải có trong CURATED_KOCS
```
Thêm/bớt KOC: sửa bảng `CURATED_KOCS` (handle → tên, follower, lĩnh vực) trong
`app/sources/tiktok_oembed.py`.

## Kiến trúc

```
Nguồn dữ liệu (tiktok_oembed / real API)
        │  fetch() -> list[KocRecord]   (đã chuẩn hóa)
        ▼
   Sync service  ── UPSERT theo (platform, platform_user_id)
        │            ├─ mới        -> INSERT + snapshot
        │            ├─ đã tồn tại -> UPDATE
        │            └─ thay đổi   -> ghi 1 snapshot lịch sử
        │           ghi sync_log (cho dashboard)
        ▼
   PostgreSQL: koc / koc_snapshot / sync_log
        ▲
   FastAPI REST  ──  React (Vite) admin UI
```

- **Đồng bộ thủ công**: `POST /api/sync` (nút "Đồng bộ ngay"). Chạy **bất
  đồng bộ** — API tạo dòng `sync_log` trạng thái `running` rồi trả về NGAY
  (HTTP 202), phần fetch + UPSERT chạy ở background (`BackgroundTasks`).
  Frontend poll `/api/stats` đến khi trạng thái khác `running`. Cách này
  tránh timeout khi nguồn thật phải gọi HTTP nhiều lần.
- **Đồng bộ tự động**: APScheduler chạy mỗi `SYNC_INTERVAL_MINUTES` phút.
- Cả hai **dùng chung** hàm `run_sync()` → logic nhất quán, idempotent.
- Toàn bộ lịch sử đồng bộ xem ở `GET /api/sync-logs` (nút "Lịch sử đồng bộ").

## Cách chạy nhanh nhất (Docker)

```bash
docker compose up --build
# backend:  http://localhost:8000  (docs: /docs)
# DB seed tự động lần đầu (~32 KOC tuyển chọn, follower ≥ 500K)
```

Sau đó chạy frontend:

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173  (đã proxy /api -> :8000)
```

## Chạy local không Docker

```bash
# 1) Postgres: tạo DB 'koc' user/pass 'koc' (hoặc sửa DATABASE_URL trong .env)
# 2) Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload   # tự tạo bảng + seed lần đầu
# 3) Frontend (terminal khác)
cd frontend && npm install && npm run dev
```

## API chính

| Method | Endpoint | Mô tả |
|---|---|---|
| GET  | `/api/stats` | tổng KOC + lần đồng bộ gần nhất |
| GET  | `/api/kocs` | danh sách + lọc/sắp xếp/phân trang |
| GET  | `/api/kocs/{id}` | chi tiết + lịch sử snapshot |
| GET  | `/api/sync-logs` | lịch sử các lần đồng bộ (mới nhất trước) |
| POST | `/api/sync` | đồng bộ thủ công (chạy nền, trả về 202) |

Tham số `/api/kocs`: `q`, `min_follower`, `max_follower`, `min_revenue`,
`max_revenue`, `sort` (follower|revenue), `order` (asc|desc), `page`, `limit`.

## Kiểm thử (tests)

Bộ test dùng **SQLite trong bộ nhớ** nên chạy được mà KHÔNG cần Postgres:

```bash
cd backend
pip install -r requirements-dev.txt
pytest                       # 8 test
```

Bao phủ lõi hệ thống:
- `tests/test_sync.py` — `run_sync` xử lý đúng 3 case của đề: INSERT dữ liệu
  mới, đồng bộ lại **idempotent** (không tạo trùng / snapshot rác), ghi
  snapshot khi follower/doanh thu **thay đổi**, và rollback + log `failed`
  khi nguồn lỗi.
- `tests/test_tiktok_oembed.py` — adapter nguồn thật: map đúng field, đánh
  dấu ước lượng, ước lượng ổn định (deterministic), bỏ qua handle lỗi (mock
  HTTP nên không cần mạng).

## Tích hợp API thật

1. Đăng ký provider có dữ liệu KOC TikTok (kiểm tra free tier trước khi dùng).
2. Điền `REAL_API_BASE_URL`, `REAL_API_KEY` vào `.env`.
3. Sửa 2 chỗ `TODO` trong `app/sources/real.py` (endpoint + mapping field)
   theo đúng tài liệu provider.
4. Đặt `DATA_SOURCE=real`.

## Cấu trúc thư mục

```
backend/
  app/
    config.py        cấu hình (env)
    database.py      engine + session
    models.py        bảng koc / koc_snapshot / sync_log
    schemas.py       response Pydantic
    crud.py          truy vấn list/filter/sort/detail
    sync.py          ★ logic UPSERT + snapshot + sync_log (+ background helper)
    scheduler.py     đồng bộ tự động theo lịch
    main.py          FastAPI app + routes (sync chạy nền, /sync-logs)
    sources/         ★ adapter: base / mock / tiktok_oembed (thật) / real
  tests/             ★ pytest (SQLite, không cần Postgres)
  schema.sql         schema SQL thuần (tham khảo)
frontend/            React admin UI (Dashboard / Danh sách / Chi tiết / Lịch sử)
docker-compose.yml
```
