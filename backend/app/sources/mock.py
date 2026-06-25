import random
from decimal import Decimal
from typing import List

from app.config import settings
from app.sources.base import DataSource, KocRecord

# Bộ "người" + "niche" -> ghép lại sinh ra nhiều tên KOC duy nhất.
# Số KOC tối đa = len(_PEOPLE) * len(_NICHES). Tăng 2 danh sách này nếu cần thêm.
_PEOPLE = [
    "Linh", "Quang", "Mai", "Tuan", "Hana", "Beo", "Khang", "Trang", "Duy", "Vy",
    "Phuc", "Ngoc", "Bao", "Thao", "Long", "Suri", "Han", "Minh", "Chi", "Tien",
    "Lan", "Hieu", "Nhi", "An", "Vu", "Yen", "Kien", "My", "Dat", "Thu",
    "Bin", "Ha", "Son", "Uyen", "Tam", "Lam", "Quyen", "Hoa", "Nam", "Diep",
    "Khoa", "Trinh", "Phong", "Nga", "Loc", "Thien", "Cuong", "Anh", "Dung", "Tra",
]

# Mỗi niche gắn với một category để dữ liệu nhất quán.
_NICHES = [
    ("Beauty", "Beauty"), ("Skincare", "Beauty"), ("Makeup", "Beauty"),
    ("Food Tour", "Food"), ("Cooking", "Food"), ("Dessert", "Food"),
    ("Tech", "Tech"), ("Gadget", "Tech"), ("Gaming", "Tech"),
    ("Fashionista", "Fashion"), ("Streetwear", "Fashion"), ("Sneaker", "Fashion"),
    ("Fitness", "Fitness"), ("Yoga", "Fitness"), ("Wellness", "Fitness"),
    ("Travel", "Travel"), ("Home Decor", "Home"), ("Garden", "Home"),
    ("Finance", "Lifestyle"), ("Pet", "Lifestyle"),
]

# Chỉ Việt Nam — hệ thống hiện tập trung vào KOC Việt Nam, không lấy quốc tế.
_REGIONS = ["VN"]


def _build_catalog() -> List[tuple[str, str]]:
    """Tạo danh sách (display_name, category) duy nhất, thứ tự ỔN ĐỊNH.

    Ghép person x niche để có nhiều tổ hợp; vì thứ tự cố định nên cùng một
    index luôn cho cùng một KOC -> idempotent khi đồng bộ lại.
    """
    catalog: List[tuple[str, str]] = []
    for niche, category in _NICHES:
        for person in _PEOPLE:
            catalog.append((f"{person} {niche}", category))
    return catalog


_CATALOG = _build_catalog()
_MAX = len(_CATALOG)


class MockDataSource(DataSource):
    """Nguồn giả lập.

    Lần fetch đầu tiên tạo bộ KOC ổn định (id cố định). Các lần sau, một
    số KOC sẽ thay đổi follower/revenue ngẫu nhiên -> dùng để chứng minh
    logic 'đồng bộ khi có thay đổi' và tạo lịch sử snapshot.

    Số lượng KOC lấy từ settings.mock_koc_count (đặt qua MOCK_KOC_COUNT
    trong .env), giới hạn trong [1, số tổ hợp tên có thể sinh].
    """

    name = "mock"

    def __init__(self, seed: int | None = None, count: int | None = None):
        self._rng = random.Random(seed)
        requested = settings.mock_koc_count if count is None else count
        self.count = max(1, min(requested, _MAX))

    def fetch(self) -> List[KocRecord]:
        records: List[KocRecord] = []
        for i in range(1, self.count + 1):
            name, category = _CATALOG[i - 1]
            uid = f"tt_{1000 + i}"
            base_follower = 5_000 * i + self._rng.randint(0, 9_000)
            # biến động +-8% để mô phỏng dữ liệu cập nhật
            jitter = self._rng.uniform(-0.08, 0.08)
            follower = int(base_follower * (1 + jitter))
            revenue = Decimal(round(follower * self._rng.uniform(0.05, 0.4), 2))
            slug = name.lower().replace(" ", "_")

            records.append(KocRecord(
                platform_user_id=uid,
                username="@" + slug,
                display_name=name,
                avatar_url=f"https://i.pravatar.cc/150?u={uid}",
                channel_url=f"https://www.tiktok.com/@{name.lower().replace(' ', '')}",
                follower_count=follower,
                revenue=revenue,
                currency="USD",
                revenue_period="30d",
                category=category,
                region=self._rng.choice(_REGIONS),
                raw={"source": "mock", "index": i},
            ))
        return records
