from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


@dataclass
class KocRecord:
    """Bản ghi chuẩn hóa từ MỌI nguồn dữ liệu.

    Mọi adapter phải trả về list[KocRecord], nhờ vậy phần còn lại của hệ
    thống (sync, DB) không cần biết dữ liệu đến từ đâu.
    """
    platform_user_id: str
    display_name: str
    follower_count: int
    platform: str = "tiktok"
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    channel_url: Optional[str] = None
    revenue: Optional[Decimal] = None
    currency: str = "USD"
    revenue_period: str = "30d"
    category: Optional[str] = None
    region: Optional[str] = None
    raw: dict = field(default_factory=dict)


class DataSource(ABC):
    """Hợp đồng chung cho mọi nguồn dữ liệu."""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> List[KocRecord]:
        """Lấy danh sách KOC, trả về list[KocRecord]."""
        raise NotImplementedError
