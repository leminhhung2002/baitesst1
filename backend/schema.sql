-- =====================================================================
-- KOC DATA SYSTEM — PostgreSQL schema
-- Mục tiêu: kho dữ liệu KOC tập trung, hỗ trợ UPSERT (mới / đã tồn tại /
-- đồng bộ khi thay đổi), tìm kiếm - lọc - sắp xếp, và theo dõi đồng bộ.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Bảng chính: koc
-- 1 dòng = 1 KOC. Trạng thái MỚI NHẤT của KOC nằm ở đây.
-- ---------------------------------------------------------------------
CREATE TABLE koc (
    id                BIGSERIAL PRIMARY KEY,          -- khóa nội bộ

    -- Khóa định danh từ nguồn -> dùng để chống trùng khi đồng bộ
    platform          VARCHAR(32)  NOT NULL DEFAULT 'tiktok',
    platform_user_id  VARCHAR(128) NOT NULL,          -- id KOC bên TikTok

    -- Các trường yêu cầu trong đề bài
    username          VARCHAR(255),                   -- handle, vd @abc
    display_name      VARCHAR(255) NOT NULL,          -- "Tên KOC"
    avatar_url        TEXT,                           -- "Avatar"
    channel_url       TEXT,                           -- "Link kênh"
    follower_count    BIGINT       NOT NULL DEFAULT 0,-- "Follower"

    -- "Doanh thu" — là số ƯỚC LƯỢNG, nên tách đơn vị + kỳ thống kê
    revenue           NUMERIC(18,2),                  -- giá trị doanh thu
    currency          VARCHAR(8)   DEFAULT 'USD',
    revenue_period    VARCHAR(32)  DEFAULT '30d',     -- vd: 30d / lifetime

    -- Trường mở rộng (tùy chọn, ăn điểm "bổ sung nếu cần")
    category          VARCHAR(128),                   -- ngành hàng / niche
    region            VARCHAR(64),                    -- thị trường/quốc gia

    -- Truy vết & đồng bộ
    raw_json          JSONB,                          -- payload gốc từ nguồn
    last_synced_at    TIMESTAMPTZ,                    -- "Ngày cập nhật dữ liệu"
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- Chống trùng: 1 KOC trên 1 nền tảng chỉ có 1 dòng
    CONSTRAINT uq_koc_platform_user UNIQUE (platform, platform_user_id)
);

-- Index phục vụ tìm kiếm / lọc / sắp xếp
CREATE INDEX idx_koc_display_name_trgm
    ON koc USING gin (lower(display_name) gin_trgm_ops);   -- tìm theo tên (LIKE)
CREATE INDEX idx_koc_follower  ON koc (follower_count DESC);
CREATE INDEX idx_koc_revenue   ON koc (revenue DESC);
-- Cần extension cho gin_trgm_ops:
--   CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------
-- Bảng lịch sử: koc_snapshot
-- Mỗi lần follower/revenue THAY ĐỔI -> ghi 1 dòng. Dùng để:
--   (a) xử lý "đồng bộ khi có thay đổi"
--   (b) vẽ biểu đồ tăng trưởng ở trang chi tiết
-- ---------------------------------------------------------------------
CREATE TABLE koc_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    koc_id          BIGINT NOT NULL REFERENCES koc(id) ON DELETE CASCADE,
    follower_count  BIGINT,
    revenue         NUMERIC(18,2),
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_snapshot_koc_time ON koc_snapshot (koc_id, captured_at DESC);

-- ---------------------------------------------------------------------
-- Bảng nhật ký đồng bộ: sync_log
-- Cấp dữ liệu cho dashboard "lần đồng bộ gần nhất".
-- ---------------------------------------------------------------------
CREATE TABLE sync_log (
    id                BIGSERIAL PRIMARY KEY,
    source            VARCHAR(64)  NOT NULL,          -- vd: mock / fastmoss
    trigger_type      VARCHAR(16)  NOT NULL DEFAULT 'manual', -- manual | schedule
    status            VARCHAR(16)  NOT NULL DEFAULT 'running',-- running|success|failed
    records_fetched   INT DEFAULT 0,
    records_inserted  INT DEFAULT 0,
    records_updated   INT DEFAULT 0,
    error_message     TEXT,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ
);
CREATE INDEX idx_sync_log_started ON sync_log (started_at DESC);

-- ---------------------------------------------------------------------
-- Trigger: tự cập nhật updated_at mỗi khi UPDATE bảng koc
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_koc_updated_at
    BEFORE UPDATE ON koc
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- VÍ DỤ LOGIC UPSERT (idempotent) — dùng chung cho sync thủ công & theo lịch
-- Với mỗi record lấy về từ nguồn, chạy:
-- =====================================================================
-- INSERT INTO koc (platform, platform_user_id, username, display_name,
--                  avatar_url, channel_url, follower_count, revenue,
--                  currency, revenue_period, raw_json, last_synced_at)
-- VALUES (:platform, :pid, :username, :name, :avatar, :url, :followers,
--         :revenue, :currency, :period, :raw, now())
-- ON CONFLICT (platform, platform_user_id) DO UPDATE SET
--     username       = EXCLUDED.username,
--     display_name   = EXCLUDED.display_name,
--     avatar_url     = EXCLUDED.avatar_url,
--     channel_url    = EXCLUDED.channel_url,
--     follower_count = EXCLUDED.follower_count,
--     revenue        = EXCLUDED.revenue,
--     raw_json       = EXCLUDED.raw_json,
--     last_synced_at = now()
-- RETURNING id, (xmax = 0) AS is_insert;   -- is_insert=true => bản ghi MỚI
--
-- Sau đó, nếu follower_count HOẶC revenue khác lần gần nhất
-- -> INSERT thêm 1 dòng vào koc_snapshot.
-- =====================================================================
