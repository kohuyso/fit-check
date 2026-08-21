# FitCheck Backend & AI Engineering Guidelines

This document outlines the mandatory rules, architectural standards, and engineering conventions for the **FitCheck AI API** backend repository.

---

## 🏗️ System Architecture & Persona

- **Role**: Senior Backend Architect & AI Specialist.
- **Domain**: FitCheck AI - Smart Wardrobe Management & Intelligent Outfit Recommendation Engine.
- **Tech Stack**:
  - **Framework**: FastAPI (Python 3.10+)
  - **Database**: PostgreSQL with SQLAlchemy ORM (2.0 style)
  - **AI / Vision**: Google Gemini API & OpenAI LLM Integration (`app/services/ai_engine.py`)
  - **Color & Style Engine**: CIELAB Delta E color math & palette matching (`app/services/color_math.py`, `app/services/color_extractor.py`)
  - **Weather Context**: Real-time OpenWeather / Heuristic context integration (`app/services/weather.py`)
  - **Async Processing**: Celery & Redis (`app/services/ai_workers.py`)
  - **Storage**: AWS S3 / MinIO Object Storage (`app/services/storage.py`)
  - **Auth**: JWT Authentication (OAuth2 Bearer token, Passlib/Bcrypt)
  - **Logging**: Loguru (`app/core/logger.py`)

---

## 📐 General Engineering Rules & Best Practices

### 1. Code Quality & Typing
- **Type Hints**: All functions must have complete parameter type annotations and return type declarations.
- **Logging**: Always use `from app.core.logger import logger` instead of `print()`. Use appropriate levels (`logger.debug`, `logger.info`, `logger.warning`, `logger.error`, `logger.exception`).
- **Imports Order**:
  1. Standard library imports (e.g. `os`, `sys`, `typing`, `datetime`).
  2. Third-party dependencies (FastAPI, SQLAlchemy, Pydantic, Celery, etc.).
  3. Local module imports (`app.core`, `app.models`, `app.services`, `app.schemas`, `app.routers`).

### 2. FastAPI & Router Conventions
- **Thin Routers, Rich Services**: Keep router logic thin. Delegate business logic, AI operations, and data transformations to `app/services/`.
- **Response Schemas**: Every endpoint MUST explicitly declare a `response_model` or return a structured `JSONResponse`.
- **Dependency Injection**:
  - Database sessions: `db: Session = Depends(get_db)`
  - Authenticated user: `current_user: User = Depends(get_current_user)`
- **Error Handling**: Throw `HTTPException(status_code=..., detail=...)` with clear user-friendly messages (Vietnamese/English).
- **Tenant & User Isolation**: Always scope queries with `user_id == current_user.id` to prevent cross-tenant data leaks.

### 3. Database & SQLAlchemy 2.0 Standards
- **SQLAlchemy Models**: Place models in `app/models/`. Use explicit column types, foreign key constraints (`ondelete="CASCADE"` where appropriate), and indexed fields.
- **Query Optimization**: Prevent N+1 queries. Use `.options(joinedload(...))` or `.options(selectinload(...))` when loading relationships.
- **Transaction Safety**: Always wrap mutations in `try...except` blocks with `db.rollback()` on exception.
- **Safe Migrations**: Schema alterations in `app/main.py` lifespan must use idempotent SQL (`ADD COLUMN IF NOT EXISTS`, `ALTER COLUMN ... DROP NOT NULL`).

### 4. AI & Vision Integration Guidelines
- **API Key & Provider Fallback**: Always handle missing, invalid, or rate-limited API keys gracefully (`ai_engine.get_ai_config()`).
- **Structured LLM Output**: Prompt LLMs to return strict JSON. Parse, sanitize (strip markdown ```json blocks), and validate against Pydantic models before returning to client.
- **Color Analysis**: Utilize `app/services/color_math.py` and `app/services/color_extractor.py` for CIELAB Delta E color matching, harmony scoring, and dominant HEX color extraction.
- **Asynchronous Worker Offloading**: Offload heavy image classification or batch recommendation tasks to Celery workers (`app/services/ai_workers.py`).

### 5. Media & Storage Guidelines
- **File Validation**: Enforce MIME types (`image/jpeg`, `image/png`, `image/webp`) and maximum file size (10MB).
- **Collision-Free Keys**: Store uploads with UUID-based keys (`uploads/{user_id}/{uuid4()}.webp`).
- **Cleanup**: Clean up temporary files in `finally:` blocks.

### 6. Security & Secrets Management
- **Never Hardcode Secrets**: All API keys, database URLs, and JWT secrets must be loaded via `app/core/config.py` from `.env`.
- **Password Hashing**: Always hash passwords using bcrypt/passlib before storing in DB.
- **Masking Sensitive Data**: Ensure diagnostic endpoints never expose raw API keys or passwords.

---

## 🎯 Development Checklist Before Committing
1. ✅ **Types**: Verified type signatures and removed unhandled `None` or `Any` references.
2. ✅ **Error Handling & Fallback**: Guaranteed fallback execution when external AI or Weather services fail.
3. ✅ **Validation**: Created or updated Pydantic schema in `app/schemas/` for request/response payloads.
4. ✅ **Logs**: Replaced temporary print statements with Loguru `logger`.
5. ✅ **Security**: Ensured all user-specific data queries filter strictly by `user_id`.
6. ✅ **Verification**: Syntax checked and tested endpoints with test client or unit tests.
