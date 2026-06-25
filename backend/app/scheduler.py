from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.sync import run_sync

scheduler = BackgroundScheduler(timezone="UTC")


def _scheduled_job():
    try:
        run_sync(settings.data_source, trigger_type="schedule")
    except Exception as exc:  # noqa: BLE001
        print(f"[scheduler] sync failed: {exc}")


def start_scheduler():
    if not settings.auto_sync_enabled:
        print("[scheduler] auto-sync disabled")
        return
    scheduler.add_job(
        _scheduled_job,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="koc_sync",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[scheduler] running every {settings.sync_interval_minutes} min")
