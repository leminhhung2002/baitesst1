"""Cache avatar TikTok về đĩa rồi phục vụ từ backend.

Vì sao cần: TikTok oEmbed KHÔNG trả avatar, trang profile thì chặn bot. Nguồn
khả dĩ là unavatar.io, nhưng hot-link nó ở MỖI lần render bị giới hạn tần suất
(429 — vài chục request/ngày cho mỗi IP). Trang có 30+ KOC sẽ bắn 30+ request
một lúc -> đa số 429 -> mất ảnh.

Giải pháp ở đây: tải MỖI avatar đúng MỘT LẦN qua unavatar rồi LƯU XUỐNG ĐĨA;
các lần sau serve thẳng từ file cache, không gọi mạng nữa. Nhờ vậy mỗi handle
chỉ tốn 1 request trọn đời -> không còn dính rate-limit khi render.

Tải ổn định 100%: đăng ký key miễn phí ở unavatar.io rồi đặt UNAVATAR_KEY trong
.env (50 request/ngày, đủ cho 1 lần quét toàn bộ danh sách). Không lấy được ảnh
-> trả None -> frontend tự hiển thị avatar chữ cái (không vỡ ảnh).
"""
import os
import re
from typing import Optional

import requests

from app.config import settings

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

# Chỉ giữ ký tự an toàn cho tên file (handle TikTok chỉ gồm chữ/số/._-).
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe(handle: str) -> str:
    return _UNSAFE.sub("_", (handle or "").strip().lstrip("@"))


def cached_path(handle: str) -> Optional[str]:
    """Trả path file avatar đã cache (nếu có & khác rỗng), ngược lại None."""
    p = os.path.join(AVATAR_DIR, _safe(handle) + ".jpg")
    if os.path.exists(p) and os.path.getsize(p) > 2000:
        return p
    return None


def media_type(path: str) -> str:
    """Đoán content-type theo magic bytes (ảnh TikTok thường là WebP, không
    phải JPEG) để trình duyệt nào cũng render đúng."""
    with open(path, "rb") as f:
        head = f.read(12)
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:4] == b"\x89PNG":
        return "image/png"
    return "image/jpeg"


def _download(url: str, dest: str, sess: requests.Session) -> bool:
    img = sess.get(url, timeout=25)
    if img.status_code == 200 and len(img.content) > 2000:
        with open(dest, "wb") as f:
            f.write(img.content)
        return True
    return False


def fetch_and_cache(handle: str) -> Optional[str]:
    """Tải avatar 1 lần, lưu đĩa, trả path. Ưu tiên tikwm (trả URL avatar
    TikTok thật, không bị giới hạn gắt), fallback unavatar. Lỗi -> None."""
    cached = cached_path(handle)
    if cached:
        return cached

    h = _safe(handle)
    dest = os.path.join(AVATAR_DIR, h + ".jpg")
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})

    # 1) tikwm: lấy URL avatar TikTok thật rồi tải về
    try:
        r = sess.get("https://www.tikwm.com/api/user/info",
                     params={"unique_id": h}, timeout=25)
        user = (r.json().get("data") or {}).get("user", {})
        url = user.get("avatarMedium") or user.get("avatarLarger") \
            or user.get("avatarThumb")
        if url and _download(url, dest, sess):
            return dest
    except Exception as exc:  # noqa: BLE001
        print(f"[avatars] tikwm @{handle} lỗi: {exc}")

    # 2) fallback unavatar (đặt UNAVATAR_KEY để ổn định)
    params = {"key": settings.unavatar_key} if settings.unavatar_key else {}
    try:
        r = sess.get(f"https://unavatar.io/tiktok/{h}", params=params, timeout=20)
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and ct.startswith("image/") and len(r.content) > 2000:
            with open(dest, "wb") as f:
                f.write(r.content)
            return dest
        print(f"[avatars] @{handle}: unavatar HTTP {r.status_code} - bỏ qua")
    except Exception as exc:  # noqa: BLE001
        print(f"[avatars] unavatar @{handle} lỗi: {exc}")
    return None
