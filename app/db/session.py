from typing import Generator
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.logger import logger

# --- CẤU HÌNH POSTGRESQL ENGINE ---
if not settings.DATABASE_URL:
    logger.error("DATABASE_URL chưa được thiết lập trong môi trường!")
    raise ValueError("DATABASE_URL is not defined in environment settings.")

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- CẤU HÌNH REDIS CLIENT ---
if settings.REDIS_URL:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
else:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True
    )
