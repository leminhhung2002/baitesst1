"""Test LÕI hệ thống: run_sync xử lý đúng 3 trường hợp của đề bài.

  1. Dữ liệu mới        -> INSERT (+ 1 snapshot)
  2. Đồng bộ lại y hệt  -> UPDATE, KHÔNG tạo bản ghi/snapshot trùng (idempotent)
  3. Dữ liệu thay đổi   -> ghi thêm 1 snapshot lịch sử
"""
from decimal import Decimal

from app.models import Koc, KocSnapshot, SyncLog
from app.sources.base import DataSource, KocRecord
from app.sync import run_sync


class FakeSource(DataSource):
    """Nguồn tiêm sẵn cho test — không gọi mạng, dữ liệu do test kiểm soát."""
    name = "fake"

    def __init__(self, records):
        self._records = records

    def fetch(self):
        return self._records


def _rec(pid, follower, revenue, name=None):
    return KocRecord(
        platform_user_id=pid,
        display_name=name or f"KOC {pid}",
        follower_count=follower,
        revenue=Decimal(str(revenue)),
        username=f"@{pid}",
        avatar_url=f"https://img/{pid}",
        channel_url=f"https://tiktok.com/@{pid}",
    )


def test_first_sync_inserts(db):
    records = [_rec("a", 100, 10), _rec("b", 200, 20)]
    log = run_sync("fake", trigger_type="manual", db=db, source=FakeSource(records))

    assert log.status == "success"
    assert log.records_fetched == 2
    assert log.records_inserted == 2
    assert log.records_updated == 0
    assert db.query(Koc).count() == 2
    # mỗi KOC mới có đúng 1 snapshot khởi tạo
    assert db.query(KocSnapshot).count() == 2


def test_resync_same_data_is_idempotent(db):
    records = [_rec("a", 100, 10), _rec("b", 200, 20)]
    run_sync("fake", db=db, source=FakeSource(records))

    # đồng bộ lần 2 với DỮ LIỆU Y HỆT
    log2 = run_sync("fake", db=db, source=FakeSource(records))

    assert log2.records_inserted == 0          # không tạo trùng
    assert log2.records_updated == 2
    assert db.query(Koc).count() == 2          # vẫn 2 KOC (UNIQUE chống trùng)
    assert db.query(KocSnapshot).count() == 2  # KHÔNG sinh snapshot rác


def test_change_creates_snapshot(db):
    run_sync("fake", db=db, source=FakeSource([_rec("a", 100, 10)]))
    assert db.query(KocSnapshot).count() == 1

    # follower thay đổi -> phải ghi thêm 1 snapshot
    run_sync("fake", db=db, source=FakeSource([_rec("a", 150, 10)]))

    koc = db.query(Koc).filter_by(platform_user_id="a").one()
    assert koc.follower_count == 150
    snaps = (db.query(KocSnapshot)
             .filter_by(koc_id=koc.id)
             .order_by(KocSnapshot.id).all())
    assert len(snaps) == 2
    assert [s.follower_count for s in snaps] == [100, 150]


def test_failed_source_marks_log_failed(db):
    class BoomSource(DataSource):
        name = "boom"
        def fetch(self):
            raise RuntimeError("nguồn lỗi")

    try:
        run_sync("boom", db=db, source=BoomSource())
    except RuntimeError:
        pass

    log = db.query(SyncLog).order_by(SyncLog.id.desc()).first()
    assert log.status == "failed"
    assert "nguồn lỗi" in (log.error_message or "")
    assert db.query(Koc).count() == 0          # rollback sạch
