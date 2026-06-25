"""Logic đồng bộ - trái tim của hệ thống.

Hàm run_sync() được DÙNG CHUNG cho cả đồng bộ thủ công (API /sync) và
đồng bộ tự động (scheduler). Chỉ khác tham số trigger_type.

Xử lý 3 trường hợp đề bài:
  - Dữ liệu mới        -> INSERT
  - Dữ liệu đã tồn tại  -> UPDATE
  - Đồng bộ khi thay đổi-> nếu follower/revenue đổi thì ghi 1 snapshot
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Koc, KocSnapshot, SyncLog
from app.sources import get_source
from app.sources.base import DataSource


def run_sync(source_name: str, trigger_type: str = "manual",
             db: Session | None = None,
             source: DataSource | None = None,
             log: SyncLog | None = None) -> SyncLog:
    """Chạy một lượt đồng bộ.

    Tham số mở rộng (đều có mặc định, không phá API cũ):
      - source: tiêm sẵn 1 adapter (dùng trong unit test, khỏi gọi mạng).
      - log:    tái sử dụng 1 dòng sync_log đã tạo sẵn (cho background task —
                endpoint tạo log "running" rồi trả về ngay, worker chạy tiếp).
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    if log is None:
        log = SyncLog(source=source_name, trigger_type=trigger_type,
                      status="running")
        db.add(log)
        db.commit()
        db.refresh(log)
    else:
        log.status = "running"
        db.commit()

    inserted = updated = fetched = 0
    try:
        source = source or get_source(source_name)
        records = source.fetch()
        fetched = len(records)
        now = datetime.now(timezone.utc)

        for rec in records:
            existing = (
                db.query(Koc)
                .filter(Koc.platform == rec.platform,
                        Koc.platform_user_id == rec.platform_user_id)
                .one_or_none()
            )

            if existing is None:
                # --- DỮ LIỆU MỚI ---
                koc = Koc(
                    platform=rec.platform,
                    platform_user_id=rec.platform_user_id,
                    username=rec.username,
                    display_name=rec.display_name,
                    avatar_url=rec.avatar_url,
                    channel_url=rec.channel_url,
                    follower_count=rec.follower_count,
                    revenue=rec.revenue,
                    currency=rec.currency,
                    revenue_period=rec.revenue_period,
                    category=rec.category,
                    region=rec.region,
                    raw_json=rec.raw,
                    last_synced_at=now,
                )
                db.add(koc)
                db.flush()  # lấy koc.id
                db.add(KocSnapshot(koc_id=koc.id,
                                   follower_count=rec.follower_count,
                                   revenue=rec.revenue))
                inserted += 1
            else:
                # --- ĐÃ TỒN TẠI: phát hiện thay đổi ---
                changed = (
                    existing.follower_count != rec.follower_count
                    or existing.revenue != rec.revenue
                )
                existing.username = rec.username
                existing.display_name = rec.display_name
                existing.avatar_url = rec.avatar_url
                existing.channel_url = rec.channel_url
                existing.follower_count = rec.follower_count
                existing.revenue = rec.revenue
                existing.currency = rec.currency
                existing.revenue_period = rec.revenue_period
                existing.category = rec.category
                existing.region = rec.region
                existing.raw_json = rec.raw
                existing.last_synced_at = now

                if changed:
                    # --- ĐỒNG BỘ KHI THAY ĐỔI: ghi lịch sử ---
                    db.add(KocSnapshot(koc_id=existing.id,
                                       follower_count=rec.follower_count,
                                       revenue=rec.revenue))
                updated += 1

        log.records_fetched = fetched
        log.records_inserted = inserted
        log.records_updated = updated
        log.status = "success"
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.status = "failed"
        log.error_message = str(exc)
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
    finally:
        db.refresh(log)
        if own_session:
            db.close()

    return log


def run_sync_for_log(log_id: int, source_name: str) -> None:
    """Chạy đồng bộ trong BACKGROUND, tiếp tục một dòng sync_log có sẵn.

    Endpoint POST /api/sync tạo trước 1 dòng log "running" và trả về ngay
    (không bắt người dùng chờ). Hàm này chạy nền ở 1 session riêng, nạp lại
    dòng log đó rồi thực thi. Nuốt exception vì không có ai đợi kết quả —
    trạng thái thất bại đã được ghi vào log để dashboard hiển thị.
    """
    db = SessionLocal()
    try:
        log = db.get(SyncLog, log_id)
        if log is None:
            return
        run_sync(source_name, trigger_type=log.trigger_type, db=db, log=log)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] background sync failed: {exc}")
    finally:
        db.close()
