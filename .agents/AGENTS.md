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
  - **Async Processing**: Celery & Redis (`app/services/ai_workers.py`)
  - **Storage**: AWS S3 / S3-compatible Object Storage (`app/services/storage.py`)
  - **Auth**: JWT Authentication (OAuth2 Bearer token, Passlib/Bcrypt)
  - **Logging**: Loguru (`app/core/logger.py`)

---

## 📐 General Engineering Rules & Best Practices

### 1. Code Quality & Typing
- **Type Hints**: All functions must have complete parameter type annotations and return type declarations.
- **Logging**: Always use `from app.core.logger import logger` instead of `print()`. Use appropriate levels (`logger.debug`, `logger.info`, `logger.warning`, `logger.error`, `logger.exception`).
- **Imports**: Organize imports logically:
  1. Standard library imports.
  2. Third-party dependencies (FastAPI, SQLAlchemy, Pydantic, etc.).
  3. Local module imports (`app.core`, `app.models`, `app.services`, etc.).

### 2. FastAPI & Router Conventions
- **Endpoint Structure**: Keep router logic thin. Delegate business logic, AI operations, and data transformations to `app/services/`.
- **Response Schemas**: Every endpoint MUST explicitly declare a `response_model` or return a structured `JSONResponse`.
- **Dependency Injection**: Use `Depends(get_db)` for database sessions and `Depends(get_current_user)` for authenticated user endpoints.
- **Error Handling**: Throw `HTTPException(status_code=..., detail=...)` with clear user-friendly messages. Exception handling logic in `app/main.py` will standardise output formatting.

### 3. Database & ORM Standards
- **SQLAlchemy Models**: Place models in `app/models/`. Use explicit column types, foreign key constraints, and relationships.
- **Queries**: Avoid N+1 queries. Use `.options(joinedload(...))` or `.options(selectinload(...))` when fetching relationships in router endpoints.
- **Migrations**: Database schema updates in `app/main.py` lifespan must use safe non-destructive SQL (`ADD COLUMN IF NOT EXISTS`, `ALTER COLUMN ... DROP NOT NULL`). For major schema refactoring, write idempotent migration scripts.

### 4. AI & Vision Integration Guidelines
- **API Key & Provider Fallback**: Always handle missing or invalid API keys gracefully (`ai_engine.get_ai_config()`).
- **Structured LLM Output**: Prompt LLMs to return strict JSON arrays/objects. Parse and validate outputs against Pydantic models before returning to client.
- **Asynchronous Processing**: Offload heavy image classification or batch recommendation tasks to Celery workers (`app/services/ai_workers.py`) or async background tasks.
- **Color Processing**: Utilize `app/services/color_math.py` for color conversions, HEX parsing, and palette matching.

### 5. Security & Privacy
- **Secrets Management**: Never hardcode API keys, database URLs, or JWT secrets. Always load them from environment variables via `app/core/config.py`.
- **User Scope**: Always scope query filters by `user_id == current_user.id` to prevent unauthorized cross-tenant data access.

---

## 🎯 Development Checklist Before Committing
1. ✅ **Types**: Verified type signatures and removed unhandled `None` or `Any` references where possible.
2. ✅ **Error Handling**: Guaranteed fallback execution when external AI service fails.
3. ✅ **Validation**: Created or updated Pydantic schema in `app/schemas/` for request/response payloads.
4. ✅ **Logs**: Replaced temporary print statements with `logger`.
5. ✅ **Verification**: Code syntax checked and API tested.
