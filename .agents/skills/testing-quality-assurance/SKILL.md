---
name: testing-quality-assurance
description: Best practices for writing Pytest unit/integration tests, mocking AI engine responses, database fixtures, and testing FastAPI endpoints in FitCheck.
---

# Testing & Quality Assurance Guide

This skill governs testing strategies, test fixtures, mocking external AI services, and automated validation for `fitcheck-backend`.

## Testing Standards

- **Framework**: `pytest`, `pytest-asyncio`, `httpx` (TestClient/AsyncClient).
- **Database Testing**: Use SQLite in-memory or a dedicated PostgreSQL test container with automatic rollback after each test.
- **AI Mocking**: Never make live API calls to Google Gemini or OpenAI during CI/CD or automated test runs.

---

## Key Testing Patterns

### 1. Test Client & Database Fixtures
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### 2. Mocking AI Responses
```python
from unittest.mock import patch

@patch("app.services.ai_engine.analyze_clothing_image")
def test_ai_clothing_tagging(mock_ai, client, auth_headers):
    mock_ai.return_value = {
        "category": "Áo thun",
        "sub_category": "T-shirt",
        "dominant_colors": ["#FFFFFF"],
        "styles": ["Casual", "Minimalist"],
        "seasons": ["Summer"]
    }
    
    response = client.post("/api/v1/closet/items/analyze-image", json={"image_url": "https://example.com/shirt.jpg"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["category"] == "Áo thun"
```

### 3. Authentication Headers Fixture
Always create a reusable fixture to generate JWT bearer tokens for authorized route testing.
