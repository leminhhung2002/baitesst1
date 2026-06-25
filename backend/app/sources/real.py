"""Adapter cho API KOC THẬT (provider bên thứ ba).

==========================================================================
 BẠN CHỈ CẦN SỬA 4 KHỐI ĐÁNH DẤU [SỬA #1..#4] BÊN DƯỚI THEO TÀI LIỆU
 PROVIDER CỦA BẠN. Phần còn lại (retry, phân trang, lỗi) đã viết sẵn.
==========================================================================

Bối cảnh: TikTok không có API chính thức công khai trả doanh thu KOC bất kỳ.
Doanh thu (GMV) ở đây là số ƯỚC LƯỢNG do provider bên thứ ba cung cấp.

Cấu hình trong .env:
    DATA_SOURCE=real
    REAL_API_BASE_URL=https://api.provider.com      # KHÔNG kèm dấu / cuối
    REAL_API_KEY=xxxxxxxx
"""
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings
from app.sources.base import DataSource, KocRecord


# ====== [SỬA #1] Endpoint + cách phân trang =============================
# Tìm trong docs: đường dẫn lấy danh sách creator, tên tham số trang/cỡ trang.
LIST_PATH = "/creators"          # ví dụ: "/v1/creators", "/open/creator/list"
PAGE_PARAM = "page"              # tên tham số số trang (hoặc "offset"/"cursor")
SIZE_PARAM = "page_size"         # tên tham số cỡ trang (hoặc "limit")
PAGE_SIZE = 100                  # số bản ghi mỗi trang
MAX_PAGES = 20                   # chặn trên, tránh lặp vô hạn khi demo
# ========================================================================


def _build_session() -> requests.Session:
    """Session có retry tự động cho lỗi mạng/429/5xx."""
    s = requests.Session()
    retry = Retry(
        total=3, backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def _auth_headers() -> dict:
    # ====== [SỬA #2] Cách xác thực ======================================
    # Chọn ĐÚNG 1 kiểu theo docs provider, xóa các kiểu còn lại:
    #
    # (a) Bearer token (phổ biến nhất):
    return {"Authorization": f"Bearer {settings.real_api_key}"}
    #
    # (b) API key header riêng:
    # return {"x-api-key": settings.real_api_key}
    #
    # (c) Key truyền qua query param: trả {} ở đây, rồi thêm
    #     params["api_key"] = settings.real_api_key trong fetch().
    # ====================================================================


def _extract_items(payload: dict) -> List[dict]:
    # ====== [SỬA #3] Đường dẫn tới mảng dữ liệu trong JSON ==============
    # Ví dụ docs trả: {"code":0,"data":{"list":[...]}} -> sửa thành:
    #   return payload.get("data", {}).get("list", [])
    return payload.get("data", [])
    # ====================================================================


def _map_item(it: dict) -> Optional[KocRecord]:
    """Map 1 bản ghi provider -> KocRecord chuẩn của hệ thống.

    ====== [SỬA #4] Đổi các KEY bên phải cho khớp field provider ========
    """
    try:
        return KocRecord(
            platform_user_id=str(it["id"]),               # id duy nhất của KOC
            username=it.get("unique_id") or it.get("username"),
            display_name=(it.get("nickname")
                          or it.get("name") or "Unknown"),
            avatar_url=it.get("avatar") or it.get("avatar_url"),
            channel_url=(it.get("profile_url")
                         or _tiktok_url(it.get("unique_id"))),
            follower_count=int(it.get("follower_count")
                               or it.get("followers") or 0),
            revenue=_to_decimal(it.get("gmv") or it.get("revenue")),
            currency=it.get("currency", "USD"),
            revenue_period=it.get("period", "30d"),
            category=it.get("category"),
            region=it.get("region") or it.get("country"),
            raw=it,                                        # giữ payload gốc
        )
    except (KeyError, ValueError, TypeError) as exc:
        print(f"[real] bỏ qua bản ghi lỗi: {exc} | {it}")
        return None
    # ====================================================================


# ---- helper, không cần sửa ----
def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _tiktok_url(handle: Optional[str]) -> Optional[str]:
    return f"https://www.tiktok.com/@{handle}" if handle else None


class RealApiDataSource(DataSource):
    name = "real"

    def fetch(self) -> List[KocRecord]:
        if not settings.real_api_base_url or not settings.real_api_key:
            raise RuntimeError(
                "Chưa cấu hình REAL_API_BASE_URL / REAL_API_KEY trong .env"
            )

        session = _build_session()
        base = settings.real_api_base_url.rstrip("/")
        url = f"{base}{LIST_PATH}"
        headers = _auth_headers()

        records: List[KocRecord] = []
        for page in range(1, MAX_PAGES + 1):
            params = {PAGE_PARAM: page, SIZE_PARAM: PAGE_SIZE}
            resp = session.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            items = _extract_items(payload)
            if not items:
                break  # hết dữ liệu

            for it in items:
                rec = _map_item(it)
                if rec:
                    records.append(rec)

            if len(items) < PAGE_SIZE:
                break  # trang cuối

        print(f"[real] lấy được {len(records)} KOC")
        return records
