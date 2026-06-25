"""Test adapter tiktok_oembed: danh tính LIVE từ oEmbed + follower THẬT từ bảng
tuyển chọn + lọc theo ngưỡng follower. Mock tầng HTTP nên KHÔNG cần mạng.
"""
import app.sources.tiktok_oembed as mod
from app.sources.tiktok_oembed import TikTokOEmbedDataSource

# Bảng tuyển chọn giả dùng cho test: handle -> (tên, follower, lĩnh vực)
CURATED = {
    "khaby.lame": ("Khaby Lame", 5_000_000, "Comedy"),
    "smallfish":  ("Cá Nhỏ",     100_000,   "Lifestyle"),
}


class _Resp:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("HTTP 500")

    def json(self):
        return self._payload


class _FakeSession:
    """Trả oEmbed giả theo handle trong query param `url`."""
    def __init__(self, by_handle, fail=()):
        self.by_handle = by_handle
        self.fail = set(fail)

    def get(self, url, params=None, timeout=None):
        handle = params["url"].rsplit("@", 1)[-1]
        if handle in self.fail:
            return _Resp(None, ok=False)
        return _Resp(self.by_handle[handle])


def _src(handles, by_handle, fail=(), min_follower=0):
    """Dựng adapter đã tiêm session giả + bảng tuyển chọn giả."""
    src = TikTokOEmbedDataSource(handles=handles, curated=CURATED,
                                 min_follower=min_follower)
    # tiêm session giả (thay cho _session())
    fake = _FakeSession(by_handle, fail=fail)
    mod._session = lambda pool=10: fake  # type: ignore
    return src


def test_maps_real_fields():
    payload = {
        "author_name": "Khaby Lame",
        "author_url": "https://www.tiktok.com/@khaby.lame",
        "title": "Khaby's Creator Profile",
        "embed_product_id": "khaby.lame",
        "embed_type": "profile",
    }
    recs = _src(["khaby.lame"], {"khaby.lame": payload}).fetch()
    assert len(recs) == 1
    r = recs[0]
    assert r.display_name == "Khaby Lame"                 # TÊN THẬT từ oEmbed
    assert r.channel_url == "https://www.tiktok.com/@khaby.lame"
    assert r.platform_user_id == "khaby.lame"
    assert r.username == "@khaby.lame"
    assert r.avatar_url == "/api/avatar/khaby.lame"  # qua proxy cache backend
    assert r.follower_count == 5_000_000                  # follower THẬT (tuyển chọn)
    assert r.raw["follower_source"] == "curated_public"
    assert r.raw["estimated_revenue"] is True             # doanh thu là ước lượng
    assert r.revenue is not None and r.revenue > 0


def test_uses_curated_name_not_oembed_junk():
    # oEmbed hay trả tên rác ("userXXXX", emoji, nickname của người khác). Tên
    # hiển thị LUÔN lấy từ bảng tuyển chọn; tên oEmbed chỉ lưu trong raw_json.
    payload = {"author_name": "user00651083464", "author_url": "u"}
    r = _src(["khaby.lame"], {"khaby.lame": payload}).fetch()[0]
    assert r.display_name == "Khaby Lame"
    assert r.raw["oembed"]["author_name"] == "user00651083464"


def test_revenue_is_deterministic():
    payload = {"author_name": "Khaby Lame", "author_url": "u"}
    a = _src(["khaby.lame"], {"khaby.lame": payload}).fetch()[0]
    b = _src(["khaby.lame"], {"khaby.lame": payload}).fetch()[0]
    # cùng handle -> cùng số liệu => đồng bộ lại không tạo snapshot rác
    assert a.follower_count == b.follower_count
    assert a.revenue == b.revenue


def test_filters_below_min_follower():
    payload = {"author_name": "n", "author_url": "u"}
    by = {"khaby.lame": payload, "smallfish": payload}
    recs = _src(["khaby.lame", "smallfish"], by, min_follower=1_000_000).fetch()
    # smallfish (100K) < ngưỡng 1M -> bị loại; chỉ còn khaby.lame (5M)
    assert [r.platform_user_id for r in recs] == ["khaby.lame"]


def test_skips_non_curated_handle():
    payload = {"author_name": "n", "author_url": "u"}
    # "unknown" không có trong bảng tuyển chọn -> không bịa follower -> bỏ qua
    recs = _src(["unknown", "khaby.lame"],
                {"unknown": payload, "khaby.lame": payload}).fetch()
    assert [r.platform_user_id for r in recs] == ["khaby.lame"]


def test_skips_failed_oembed():
    payload = {"author_name": "OK", "author_url": "u"}
    recs = _src(["smallfish", "khaby.lame"],
                {"khaby.lame": payload}, fail=["smallfish"]).fetch()
    assert [r.platform_user_id for r in recs] == ["khaby.lame"]  # bỏ handle lỗi


def test_raises_when_all_skipped():
    try:
        _src(["unknown1", "unknown2"], {}).fetch()  # không handle nào trong bảng
        assert False, "phải raise khi không giữ được KOC nào"
    except RuntimeError:
        pass
