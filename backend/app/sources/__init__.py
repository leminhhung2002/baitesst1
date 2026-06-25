from app.sources.base import DataSource
from app.sources.mock import MockDataSource
from app.sources.real import RealApiDataSource
from app.sources.tiktok_oembed import TikTokOEmbedDataSource
from app.sources.tiktok_top import TikTokTopDataSource


def get_source(name: str) -> DataSource:
    name = (name or "tiktok_top").lower()
    if name == "tiktok_top":
        return TikTokTopDataSource()
    if name == "tiktok_oembed":
        return TikTokOEmbedDataSource()
    if name == "mock":
        return MockDataSource()
    if name == "real":
        return RealApiDataSource()
    raise ValueError(f"Unknown data source: {name}")
