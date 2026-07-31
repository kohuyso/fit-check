import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
# 1. Import thêm thư viện Redis
import redis

load_dotenv()

# --- CẤU HÌNH POSTGRESQL ---
DATABASE_URL = os.getenv("DATABASE_URL") 

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not defined")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- CẤU HÌNH REDIS CLIENT ---
REDIS_URL = os.getenv("REDIS_URL")

if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
else:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )