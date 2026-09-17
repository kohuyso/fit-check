"""
Database & Session Shim for backward compatibility.
All database engine, sessions, and dependencies are now modularized under:
- app.db.base (Base model)
- app.db.session (engine, SessionLocal, redis_client)
- app.api.deps (get_db, get_current_user, get_redis)
"""
from app.db.base import Base
from app.db.session import engine, SessionLocal, redis_client
from app.api.deps import get_db

__all__ = ["Base", "engine", "SessionLocal", "redis_client", "get_db"]