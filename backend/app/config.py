from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL. Override bằng biến môi trường khi deploy.
    database_url: str = "postgresql+psycopg2://koc:koc@localhost:5432/koc"

    # Nguồn dữ liệu mặc định:
    #   "tiktok_top"    -> ~90 KOC VN THẬT từ bảng xếp hạng follower + avatar thật
    #   "tiktok_oembed" -> danh tính live qua oEmbed + follower từ bảng tuyển chọn
    #   "real"          -> provider bên thứ ba (cần API key, template real.py)
    data_source: str = "tiktok_top"

    # Nếu seed lần đầu bằng nguồn thật THẤT BẠI -> tự seed bằng nguồn này để UI
    # không trống. Để RỖNG = tắt fallback (không dùng mock nữa).
    seed_fallback_source: str = ""

    # Danh sách handle TikTok cho nguồn tiktok_oembed (ngăn cách bởi dấu phẩy,
    # không kèm @). Để trống -> dùng danh sách TUYỂN CHỌN trong adapter.
    tiktok_handles: str = ""

    # Ngưỡng lọc follower: KOC dưới ngưỡng này bị loại khi đồng bộ (loại người
    # ít follower / không xứng đáng là KOC). Mặc định 500K.
    min_follower: int = 500_000

    # Số KOC sinh ra ở nguồn "mock". Tăng để demo với nhiều dữ liệu hơn.
    # Tối đa = số người * số niche trong mock.py (hiện ~800).
    mock_koc_count: int = 120

    # Đồng bộ tự động: bật/tắt + chu kỳ (phút)
    auto_sync_enabled: bool = True
    sync_interval_minutes: int = 60

    # Tự seed dữ liệu khi khởi động nếu DB trống
    seed_on_startup: bool = True

    # Cho frontend gọi (CORS). Đổi theo domain deploy.
    cors_origins: str = "http://localhost:5173"

    # Key unavatar.io (tuỳ chọn, miễn phí) để tải avatar TikTok ỔN ĐỊNH. Để
    # trống -> tải ẩn danh (bị giới hạn tần suất, đa số sẽ là avatar chữ cái).
    unavatar_key: str = ""

    # ----- Provider thật (điền khi tích hợp API thật) -----
    real_api_base_url: str = ""
    real_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
