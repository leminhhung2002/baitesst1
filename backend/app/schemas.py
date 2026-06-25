from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class KocBase(BaseModel):
    id: int
    platform: str
    platform_user_id: str
    username: Optional[str] = None
    display_name: str
    avatar_url: Optional[str] = None
    channel_url: Optional[str] = None
    follower_count: int
    revenue: Optional[Decimal] = None
    currency: Optional[str] = None
    revenue_period: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None
    last_synced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SnapshotOut(BaseModel):
    follower_count: Optional[int] = None
    revenue: Optional[Decimal] = None
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KocDetail(KocBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    snapshots: List[SnapshotOut] = []


class KocListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[KocBase]


class SyncLogOut(BaseModel):
    id: int
    source: str
    trigger_type: str
    status: str
    records_fetched: int
    records_inserted: int
    records_updated: int
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StatsOut(BaseModel):
    total_koc: int
    last_sync: Optional[SyncLogOut] = None
