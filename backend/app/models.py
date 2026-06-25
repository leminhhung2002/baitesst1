from datetime import datetime

from sqlalchemy import (
    JSON, BigInteger, Column, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base

# Trên PostgreSQL dùng BIGINT/JSONB (như production). Khi chạy test bằng
# SQLite, BigInteger auto-increment và JSONB không hỗ trợ -> đổi biến thể
# sang INTEGER/JSON để bộ test chạy được mà không cần Postgres.
PK = BigInteger().with_variant(Integer, "sqlite")
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Koc(Base):
    __tablename__ = "koc"

    id = Column(PK, primary_key=True)

    platform = Column(String(32), nullable=False, default="tiktok")
    platform_user_id = Column(String(128), nullable=False)

    username = Column(String(255))
    display_name = Column(String(255), nullable=False)
    avatar_url = Column(Text)
    channel_url = Column(Text)
    follower_count = Column(BigInteger, nullable=False, default=0)

    revenue = Column(Numeric(18, 2))
    currency = Column(String(8), default="USD")
    revenue_period = Column(String(32), default="30d")

    category = Column(String(128))
    region = Column(String(64))

    raw_json = Column(JSON_TYPE)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    snapshots = relationship("KocSnapshot", back_populates="koc",
                             cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id",
                         name="uq_koc_platform_user"),
    )


class KocSnapshot(Base):
    __tablename__ = "koc_snapshot"

    id = Column(PK, primary_key=True)
    koc_id = Column(PK, ForeignKey("koc.id", ondelete="CASCADE"),
                    nullable=False)
    follower_count = Column(BigInteger)
    revenue = Column(Numeric(18, 2))
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    koc = relationship("Koc", back_populates="snapshots")


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(PK, primary_key=True)
    source = Column(String(64), nullable=False)
    trigger_type = Column(String(16), nullable=False, default="manual")
    status = Column(String(16), nullable=False, default="running")
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
