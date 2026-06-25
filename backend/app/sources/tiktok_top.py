"""Nguồn dữ liệu KOC: ~100 KOC cá nhân VN, LẤY FOLLOWER LIVE mỗi lần đồng bộ.

Danh sách AI để theo dõi: `app/data/koc_top_vn.json` (handle, tên, lĩnh vực) —
gốc từ bảng xếp hạng follower công khai + danh sách tuyển chọn, đã loại nick
giả mạo & tài khoản brand/media (chỉ giữ KOC cá nhân).

SỐ FOLLOWER lấy LIVE qua API công khai tikwm mỗi lần đồng bộ:
  - Nhờ vậy follower THAY ĐỔI thật theo thời gian -> mỗi lần đồng bộ phát hiện
    thay đổi -> ghi 1 snapshot -> BIỂU ĐỒ tăng trưởng tự đầy lên (đúng "cách 1":
    đồng bộ định kỳ, lịch sử tích lũy thật, KHÔNG bịa số).
  - tikwm cũng cấp URL avatar TikTok thật (đã cache ở backend, xem app/avatars.py).
Handle nào tikwm lỗi -> fallback số follower trong JSON (KOC vẫn hiện, không rớt).

Doanh thu: KHÔNG có nguồn công khai -> ước lượng ổn định theo follower, đánh dấu
`raw_json["estimated_revenue"]=true`.
"""
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings
from app.sources.base import DataSource, KocRecord

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "koc_top_vn.json")
TIKWM_URL = "https://www.tikwm.com/api/user/info"

DEFAULT_REGION = "VN"
DATA_AS_OF = "2026-06"


def _estimate_revenue(handle: str, follower: int) -> Decimal:
    """Ước lượng doanh thu ỔN ĐỊNH theo follower (hash -> hệ số 2%..8%)."""
    h = int(hashlib.sha256(handle.encode()).hexdigest(), 16)
    factor = 0.02 + (h % 7) / 100
    return Decimal(str(round(follower * factor, 2)))


def _load() -> List[dict]:
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=0.8,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=8,
                                    pool_maxsize=8))
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s


class TikTokTopDataSource(DataSource):
    name = "tiktok_top"

    def __init__(self, rows: Optional[List[dict]] = None,
                 min_follower: Optional[int] = None, live: bool = True):
        self.rows = rows if rows is not None else _load()
        self.min_follower = (min_follower if min_follower is not None
                             else settings.min_follower)
        self.live = live          # đặt False để dùng số trong JSON (test/offline)

    def _live_follower(self, sess: requests.Session,
                       handle: str) -> Optional[int]:
        """Lấy follower LIVE từ tikwm. Lỗi -> None (sẽ fallback JSON).

        Có nghỉ ngắn sau mỗi gọi vì tikwm giới hạn tần suất (gọi dồn -> 429).
        """
        try:
            r = sess.get(TIKWM_URL, params={"unique_id": handle}, timeout=20)
            j = r.json()
            time.sleep(0.35)
            if j.get("code") == 0:
                return int(j["data"]["stats"]["followerCount"])
        except Exception as exc:  # noqa: BLE001
            print(f"[tiktok_top] tikwm @{handle} lỗi: {exc}")
        return None

    def fetch(self) -> List[KocRecord]:
        live: dict[str, int] = {}
        if self.live:
            sess = _session()
            # workers thấp + nghỉ ngắn -> ~2 req/s, tránh 429 của tikwm khi quét
            # cả trăm handle (đổi lại mỗi lần sync mất ~1 phút, chấp nhận được
            # vì sync chạy nền + theo lịch).
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = {pool.submit(self._live_follower, sess, r["handle"]): r["handle"]
                        for r in self.rows}
                for fut in as_completed(futs):
                    val = fut.result()
                    if val:
                        live[futs[fut]] = val

        records: List[KocRecord] = []
        skipped = 0
        for r in self.rows:
            handle = r["handle"]
            # follower LIVE nếu lấy được, không thì dùng số trong JSON
            follower = live.get(handle, int(r["followers"]))
            if follower < self.min_follower:
                skipped += 1
                continue
            records.append(KocRecord(
                platform="tiktok",
                platform_user_id=handle,
                username="@" + handle,
                display_name=r["name"],
                avatar_url=f"/api/avatar/{handle}",
                channel_url=f"https://www.tiktok.com/@{handle}",
                follower_count=follower,
                revenue=_estimate_revenue(handle, follower),
                currency="USD",
                revenue_period="30d",
                category=r.get("category"),
                region=DEFAULT_REGION,
                raw={
                    "follower_source": "tikwm_live" if handle in live else "leaderboard_fallback",
                    "follower_as_of": DATA_AS_OF,
                    "estimated_revenue": True,
                },
            ))

        records.sort(key=lambda x: (-x.follower_count, x.platform_user_id))
        print(f"[tiktok_top] giữ {len(records)} KOC "
              f"(follower live {len(live)}/{len(self.rows)}), bỏ {skipped}")
        if not records:
            raise RuntimeError("koc_top_vn.json rỗng hoặc tất cả dưới ngưỡng.")
        return records
