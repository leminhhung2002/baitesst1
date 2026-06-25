from typing import Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.models import Koc, SyncLog


SORTABLE = {"follower": Koc.follower_count, "revenue": Koc.revenue}


def list_kocs(db: Session, *, q: Optional[str] = None,
              min_follower: Optional[int] = None,
              max_follower: Optional[int] = None,
              min_revenue: Optional[float] = None,
              max_revenue: Optional[float] = None,
              sort: str = "follower", order: str = "desc",
              page: int = 1, limit: int = 20):
    query = db.query(Koc)

    if q:
        query = query.filter(Koc.display_name.ilike(f"%{q}%"))
    if min_follower is not None:
        query = query.filter(Koc.follower_count >= min_follower)
    if max_follower is not None:
        query = query.filter(Koc.follower_count <= max_follower)
    if min_revenue is not None:
        query = query.filter(Koc.revenue >= min_revenue)
    if max_revenue is not None:
        query = query.filter(Koc.revenue <= max_revenue)

    total = query.count()

    col = SORTABLE.get(sort, Koc.follower_count)
    query = query.order_by(asc(col) if order == "asc" else desc(col))

    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    items = query.offset((page - 1) * limit).limit(limit).all()

    return total, page, limit, items


def get_koc(db: Session, koc_id: int) -> Optional[Koc]:
    return db.query(Koc).filter(Koc.id == koc_id).one_or_none()


def get_stats(db: Session):
    total = db.query(Koc).count()
    last = (db.query(SyncLog)
            .order_by(SyncLog.started_at.desc())
            .first())
    return total, last


def list_sync_logs(db: Session, limit: int = 20):
    limit = min(max(limit, 1), 100)
    return (db.query(SyncLog)
            .order_by(SyncLog.started_at.desc())
            .limit(limit)
            .all())
