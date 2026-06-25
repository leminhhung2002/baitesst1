"""Cấu hình test: dùng SQLite trong bộ nhớ -> chạy được mà KHÔNG cần Postgres.

Models đã khai báo biến thể (BigInteger->Integer, JSONB->JSON) cho SQLite nên
toàn bộ schema tạo được trên SQLite. Mỗi test nhận 1 session sạch.
"""
import os

# Trỏ DB sang SQLite TRƯỚC khi import app -> engine không nạp psycopg2,
# nên bộ test chạy được dù máy không cài driver Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("AUTO_SYNC_ENABLED", "false")
os.environ.setdefault("SEED_ON_STARTUP", "false")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401  (đăng ký bảng vào Base.metadata)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
