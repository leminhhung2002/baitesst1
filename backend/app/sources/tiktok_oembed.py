"""Adapter dữ liệu KOC từ TikTok — danh sách TUYỂN CHỌN + follower THẬT.

Bối cảnh (đã kiểm chứng bằng cách gọi API thật 2026-06):
  - TikTok oEmbed (https://www.tiktok.com/oembed) là endpoint CÔNG KHAI,
    KHÔNG cần key, nhưng CHỈ trả về: tên hiển thị (author_name) + link kênh
    (author_url) + xác nhận hồ sơ tồn tại. **KHÔNG có follower, doanh thu,
    avatar.**
  - Tải trang profile để bóc `followerCount` thì bị TikTok chặn bot
    (SlardarWAF). Không có nguồn MIỄN PHÍ nào trả follower KOC.

Vì vậy adapter này dùng cách TRUNG THỰC cho một bản demo không tốn phí:
  - **Danh tính (tên/link/avatar) lấy LIVE & THẬT**: tên + link từ oEmbed,
    avatar qua unavatar.io. Mỗi lần đồng bộ đều gọi oEmbed để xác minh hồ sơ
    còn sống.
  - **Follower lấy từ bảng TUYỂN CHỌN `CURATED_KOCS`**: số follower công khai,
    xấp xỉ, cập nhật tay tại `CURATED_AS_OF`. Chỉ những KOC có thật, nhiều
    follower mới nằm trong bảng này -> tự động loại người ít follower / vô danh.
  - **Doanh thu vẫn là ƯỚC LƯỢNG** (không có nguồn công khai), suy ra ổn định
    từ follower và đánh dấu `raw_json["estimated_revenue"]=true`.
  - Áp NGƯỠNG `MIN_FOLLOWER` (mặc định 500K) -> handle dưới ngưỡng bị loại.
  - Handle KHÔNG có trong bảng tuyển chọn -> bỏ qua (không bịa số follower).

Cấu hình (.env):
    DATA_SOURCE=tiktok_oembed
    MIN_FOLLOWER=500000                 # ngưỡng lọc follower
    TIKTOK_HANDLES=                      # để trống -> dùng danh sách tuyển chọn
    TIKTOK_FETCH_WORKERS=8               # số luồng song song
"""
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings
from app.sources.base import DataSource, KocRecord

OEMBED_URL = "https://www.tiktok.com/oembed"

# Mọi KOC trong bảng dưới đây là creator VIỆT NAM -> đánh dấu region "VN".
DEFAULT_REGION = "VN"

# Ngày tuyển chọn số follower (cập nhật tay). Hiển thị để minh bạch nguồn số.
CURATED_AS_OF = "2026-06"

# ---------------------------------------------------------------------------
# DANH SÁCH TUYỂN CHỌN: handle -> (tên hiển thị, follower xấp xỉ, lĩnh vực).
#
# Mỗi handle đã được XÁC MINH bằng 2 tín hiệu (06/2026):
#   (1) Tra cứu web -> đúng tài khoản CHÍNH CHỦ (tick xanh / nhiều follower
#       nhất), loại nick fan/giả mạo.
#   (2) Gọi oEmbed -> tên hồ sơ TikTok trả về KHỚP với KOC.
# Follower là số CÔNG KHAI, XẤP XỈ tại CURATED_AS_OF (đơn vị: người), lấy từ
# kết quả tra cứu. Lưu ý vài handle chính chủ KHÔNG trùng tên (vd Phạm Thoại
# bán hàng dưới @norinpham_m4, Độ Mixi dùng @mixigaming). Thêm/bớt: sửa ở đây.
# ---------------------------------------------------------------------------
CURATED_KOCS: Dict[str, Tuple[str, int, str]] = {
    # --- Gia đình / Hài / Giải trí ---
    "giadinhcamcam":            ("Gia Đình Cam Cam",  720_000, "Gia đình / Giải trí"),
    "duongbaolam":              ("Lê Dương Bảo Lâm", 6_300_000, "Hài / Giải trí"),
    "longchunchun":             ("Long Chun",        6_600_000, "Hài / Giải trí"),
    "hauhoang":                 ("Hậu Hoàng",        6_300_000, "Hài / Giải trí"),
    "crisdevilgamer7":          ("CrisDevilGamer",   6_000_000, "Hài / Giải trí"),
    "lebong95":                 ("Lê Bống",         10_100_000, "Hài / Giải trí"),
    "letuankhang2002":          ("Lê Tuấn Khang",   11_500_000, "Hài / Giải trí"),
    "truonggiang.channel":      ("Trường Giang",     2_500_000, "Hài / Giải trí"),
    # --- MC / Giải trí ---
    "tranthanh123":             ("Trấn Thành",       7_600_000, "MC / Giải trí"),
    "khanhvyccf":               ("Khánh Vy",         2_600_000, "MC / Giải trí"),
    "tunpham97":                ("Tun Phạm",         4_700_000, "MC / Giải trí"),
    # --- Bán hàng / Review (KOC thương mại điển hình) ---
    "norinpham_m4":             ("Phạm Thoại",       5_700_000, "Bán hàng / Review"),
    "hangkat6668":              ("Hằng Du Mục",      4_100_000, "Bán hàng / Review"),
    "halinhofficial":           ("Võ Hà Linh",       4_000_000, "Beauty / Review"),
    # --- Beauty / Thời trang / Lifestyle ---
    "chaubui":                  ("Châu Bùi",         2_000_000, "Thời trang"),
    "quynhanhshyn_":            ("Quỳnh Anh Shyn",   1_400_000, "Thời trang"),
    "salimhwg":                 ("Salim",            1_200_000, "Lifestyle"),
    "jenny.huynh._":            ("Jenny Huỳnh",      7_300_000, "Lifestyle"),
    # --- Ẩm thực / Du lịch ---
    "khoailangthang":           ("Khoai Lang Thang", 3_100_000, "Du lịch"),
    "quynhtranjp_official":     ("Quỳnh Trần JP",    1_100_000, "Ẩm thực"),
    "batanvlog01":              ("Bà Tân Vlog",      1_600_000, "Ẩm thực"),
    # --- Streamer / Gaming ---
    "mixigaming":               ("Độ Mixi",          6_800_000, "Streamer"),
    "mcmisthy":                 ("MisThy",           5_100_000, "Streamer"),
    "dramakinglndx":            ("Linh Ngọc Đàm",    5_100_000, "Streamer"),
    "virussvn":                 ("ViruSs",           1_900_000, "Streamer"),
    # --- Ca sĩ / Rapper / Nghệ sĩ ---
    "capyboiii_7":              ("Sơn Tùng M-TP",    7_000_000, "Ca sĩ"),
    "hoaminzy_hoadambut":       ("Hòa Minzy",        7_100_000, "Ca sĩ"),
    "chipupu":                  ("Chi Pu",           3_400_000, "Ca sĩ / Diễn viên"),
    "huonggiangofficial":       ("Hương Giang",      4_600_000, "Ca sĩ"),
    "phuongmychiofficial":      ("Phương Mỹ Chi",    5_400_000, "Ca sĩ"),
    "erikkkofficial":           ("ERIK",             2_400_000, "Ca sĩ"),
    "soobin.hoangson_official": ("SOOBIN",           1_500_000, "Ca sĩ"),
    "minhhang2206":             ("Minh Hằng",        1_300_000, "Ca sĩ / Diễn viên"),
    "hariwonday":               ("Hari Won",         2_500_000, "Ca sĩ / MC"),
    "mleeofficial":             ("MLee",               900_000, "Ca sĩ / Diễn viên"),
    "hieuthuhai2222":           ("HIEUTHUHAI",       3_400_000, "Rapper"),
    "phaoxinhxinh":             ("Pháo Northside",   1_700_000, "Rapper"),
    "lf.tlinh":                 ("tlinh",            1_800_000, "Rapper"),
}


def _session(pool: int = 10) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=1.0,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool,
                          pool_maxsize=pool)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": "KOC-Data-System/1.0 (+demo)"})
    return s


def _estimate_revenue(handle: str, follower: int) -> Decimal:
    """Ước lượng doanh thu ỔN ĐỊNH từ follower (không có nguồn công khai).

    Dùng hash(handle) -> hệ số 2%..8% giá trị/follower, cố định theo handle nên
    đồng bộ lại KHÔNG tạo snapshot rác. follower là số THẬT (tuyển chọn) nên
    doanh thu suy ra cũng tỉ lệ hợp lý. Vẫn đánh dấu là ƯỚC LƯỢNG.
    """
    h = int(hashlib.sha256(handle.encode()).hexdigest(), 16)
    factor = 0.02 + (h % 7) / 100        # 0.02 .. 0.08 USD / follower / 30d
    return Decimal(str(round(follower * factor, 2)))


def _workers() -> int:
    """Số luồng song song khi fetch (đặt qua TIKTOK_FETCH_WORKERS)."""
    try:
        return max(1, int(os.environ.get("TIKTOK_FETCH_WORKERS", "8")))
    except ValueError:
        return 8


class TikTokOEmbedDataSource(DataSource):
    name = "tiktok_oembed"

    def __init__(self, handles: Optional[List[str]] = None,
                 curated: Optional[Dict[str, Tuple[str, int, str]]] = None,
                 min_follower: Optional[int] = None):
        self.curated = curated if curated is not None else CURATED_KOCS
        self.min_follower = (min_follower if min_follower is not None
                             else settings.min_follower)

        raw = handles if handles is not None else _parse_handles(
            settings.tiktok_handles, list(self.curated.keys()))
        # bỏ trùng nhưng giữ thứ tự
        seen: set[str] = set()
        self.handles = []
        for h in raw:
            h = h.strip().lstrip("@")
            if h and h not in seen:
                seen.add(h)
                self.handles.append(h)

    def _fetch_one(self, sess: requests.Session,
                   handle: str) -> Optional[KocRecord]:
        info = self.curated.get(handle)
        if info is None:
            # Không có follower THẬT cho handle này -> không bịa số, bỏ qua.
            print(f"[tiktok_oembed] skip @{handle}: chưa có trong "
                  f"CURATED_KOCS (thiếu follower thật)")
            return None

        curated_name, follower, category = info
        if follower < self.min_follower:
            print(f"[tiktok_oembed] skip @{handle}: follower {follower:,} < "
                  f"ngưỡng {self.min_follower:,}")
            return None

        profile_url = f"https://www.tiktok.com/@{handle}"
        try:
            resp = sess.get(OEMBED_URL, params={"url": profile_url}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            print(f"[tiktok_oembed] skip @{handle}: {exc}")
            return None

        # Tên hiển thị: dùng TÊN TUYỂN CHỌN làm chuẩn (đã xác minh là đúng KOC).
        # oEmbed thường trả author_name dạng "userXXXX", emoji, hoặc nickname
        # lạ -> không dùng làm tên hiển thị, chỉ lưu lại trong raw_json để minh
        # bạch. oEmbed ở đây đóng vai trò xác minh hồ sơ còn sống + lấy link kênh.
        display_name = curated_name

        revenue = _estimate_revenue(handle, follower)
        return KocRecord(
            platform="tiktok",
            platform_user_id=handle,                       # định danh ổn định
            username="@" + handle,
            display_name=display_name,
            avatar_url=f"/api/avatar/{handle}",  # qua proxy cache của backend
            channel_url=data.get("author_url") or profile_url,  # KÊNH THẬT
            follower_count=follower,                       # THẬT (tuyển chọn)
            revenue=revenue,                               # ước lượng
            currency="USD",
            revenue_period="30d",
            category=category,
            region=DEFAULT_REGION,
            raw={
                "oembed": {k: data.get(k) for k in
                           ("title", "author_name", "author_url",
                            "embed_product_id", "embed_type")},
                "follower_source": "curated_public",  # follower từ bảng tuyển chọn
                "follower_as_of": CURATED_AS_OF,
                "estimated_revenue": True,            # doanh thu là ước lượng
            },
        )

    def fetch(self) -> List[KocRecord]:
        sess = _session(pool=_workers())
        records: List[KocRecord] = []
        skipped = 0

        # Fetch song song nhiều handle cho nhanh; lỗi/loại từng handle -> bỏ qua.
        with ThreadPoolExecutor(max_workers=_workers()) as pool:
            futures = {pool.submit(self._fetch_one, sess, h): h
                       for h in self.handles}
            for fut in as_completed(futures):
                rec = fut.result()
                if rec is not None:
                    records.append(rec)
                else:
                    skipped += 1

        # sắp theo follower giảm dần cho kết quả trực quan & ổn định
        records.sort(key=lambda r: (-r.follower_count, r.platform_user_id))

        print(f"[tiktok_oembed] giữ {len(records)} KOC "
              f"(ngưỡng {self.min_follower:,} follower), bỏ {skipped}")
        if not records:
            raise RuntimeError(
                "Không lấy được KOC nào (kiểm tra mạng, CURATED_KOCS, "
                "MIN_FOLLOWER hoặc danh sách TIKTOK_HANDLES)."
            )
        return records


def _parse_handles(value: str, default: List[str]) -> List[str]:
    value = (value or "").strip()
    if not value:
        return default
    return value.split(",")
