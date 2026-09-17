import os
import sys
from typing import Generator
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector

# Đảm bảo import được module app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Cho phép SQLite xử lý kiểu Vector của pgvector như kiểu TEXT trong quá trình test
@compiles(Vector, 'sqlite')
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

os.environ["TESTING"] = "true"
from app.main import app

from app.db.base import Base
from app.api.deps import get_db, get_redis
from app.core import security
from app.models.user import User

# Sử dụng SQLite file tạm hoặc in-memory cho test suite
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_suite.db"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

class MockRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(str(key))

    def set(self, key, value, *args, **kwargs):
        self.store[str(key)] = str(value)
        return True

    def setex(self, key, time, value):
        self.store[str(key)] = str(value)
        return True

    def exists(self, key):
        return str(key) in self.store

    def delete(self, *keys):
        count = 0
        for k in keys:
            if str(k) in self.store:
                del self.store[str(k)]
                count += 1
        return count

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_suite.db"):
        try:
            os.remove("./test_suite.db")
        except OSError:
            pass

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def mock_redis():
    return MockRedis()

@pytest.fixture(scope="function")
def client(db_session: Session, mock_redis: MockRedis) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Disable rate limiting during automated test suite execution
    original_limiter_enabled = getattr(app.state.limiter, "enabled", True)
    app.state.limiter.enabled = False

    with TestClient(app) as test_client:
        yield test_client

    app.state.limiter.enabled = original_limiter_enabled
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    user = db_session.query(User).filter(User.email == "testuser@fitcheck.ai").first()
    if not user:
        user = User(
            email="testuser@fitcheck.ai",
            hashed_password=security.get_password_hash("TestPassword123!"),
            full_name="Tester FitCheck",
            is_active=True,
            preferred_style=["Casual", "Formal"]
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(test_user: User) -> dict:
    access_token = security.create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {access_token}"}
