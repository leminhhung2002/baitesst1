import sys
from typing import List, Optional

# Ép stdout/stderr về UTF-8 (errors=replace) để các log tiếng Việt không làm
# crash tiến trình trên console Windows (mặc định cp1252). An toàn trên mọi OS.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from fastapi import (
    BackgroundTasks, Depends, FastAPI, HTTPException, Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import avatars, crud, schemas
from app.config import settings
from app.database import Base, engine, get_db
from app.models import SyncLog
from app.scheduler import start_scheduler
from app.sync import run_sync, run_sync_for_log

app = FastAPI(title="KOC Data System", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        from app.models import Koc
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            if db.query(Koc).count() == 0:
                print(f"[startup] DB empty -> seed via '{settings.data_source}'")
                try:
                    run_sync(settings.data_source, trigger_type="manual", db=db)
                except Exception as exc:  # noqa: BLE001
                    fb = settings.seed_fallback_source
                    if fb and fb != settings.data_source:
                        print(f"[startup] seed failed ({exc}); fallback -> '{fb}'")
                        run_sync(fb, trigger_type="manual", db=db)
                    else:
                        print(f"[startup] seed failed ({exc}); no fallback")
        finally:
            db.close()
    start_scheduler()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/avatar/{handle}")
def get_avatar(handle: str):
    """Avatar TikTok đã cache về đĩa (tải 1 lần qua unavatar). Không có ->
    404 để frontend tự hiển thị avatar chữ cái, KHÔNG bắn request mỗi lần render.
    """
    path = avatars.cached_path(handle) or avatars.fetch_and_cache(handle)
    if not path:
        raise HTTPException(status_code=404, detail="no avatar")
    return FileResponse(path, media_type=avatars.media_type(path),
                        headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/kocs", response_model=schemas.KocListResponse)
def list_kocs(
    q: Optional[str] = None,
    min_follower: Optional[int] = None,
    max_follower: Optional[int] = None,
    min_revenue: Optional[float] = None,
    max_revenue: Optional[float] = None,
    sort: str = Query("follower", pattern="^(follower|revenue)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    total, page, limit, items = crud.list_kocs(
        db, q=q, min_follower=min_follower, max_follower=max_follower,
        min_revenue=min_revenue, max_revenue=max_revenue,
        sort=sort, order=order, page=page, limit=limit,
    )
    return {"total": total, "page": page, "limit": limit, "items": items}


@app.get("/api/kocs/{koc_id}", response_model=schemas.KocDetail)
def get_koc(koc_id: int, db: Session = Depends(get_db)):
    koc = crud.get_koc(db, koc_id)
    if not koc:
        raise HTTPException(status_code=404, detail="KOC not found")
    # sắp xếp snapshot theo thời gian tăng dần cho biểu đồ
    koc.snapshots.sort(key=lambda s: s.captured_at)
    return koc


@app.get("/api/stats", response_model=schemas.StatsOut)
def stats(db: Session = Depends(get_db)):
    total, last = crud.get_stats(db)
    return {"total_koc": total, "last_sync": last}


@app.get("/api/sync-logs", response_model=List[schemas.SyncLogOut])
def list_sync_logs(limit: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db)):
    """Lịch sử các lần đồng bộ (mới nhất trước) cho trang theo dõi."""
    return crud.list_sync_logs(db, limit=limit)


@app.post("/api/sync", response_model=schemas.SyncLogOut, status_code=202)
def trigger_sync(background_tasks: BackgroundTasks,
                 source: Optional[str] = None,
                 db: Session = Depends(get_db)):
    """Đồng bộ THỦ CÔNG (nút 'Đồng bộ ngay').

    KHÔNG bắt người dùng chờ: tạo 1 dòng sync_log 'running', trả về NGAY
    (HTTP 202), rồi chạy phần nặng (fetch nguồn + UPSERT) ở background.
    Frontend poll /api/stats đến khi status != 'running'. Cách này quan
    trọng với nguồn thật (gọi HTTP nhiều lần) để tránh timeout request.
    """
    src = source or settings.data_source
    log = SyncLog(source=src, trigger_type="manual", status="running")
    db.add(log)
    db.commit()
    db.refresh(log)
    background_tasks.add_task(run_sync_for_log, log.id, src)
    return log
