---
name: sqlalchemy-database
description: Guidelines for managing database models, migrations, ORM relationships, session safety, and startup schema execution in FitCheck.
---

# Database & SQLAlchemy 2.0 Engineering Guide

This skill defines rules for model creation, database interactions, session lifecycles, and schema migrations.

## Database Layout

- `app/database.py`: SessionLocal factory, Engine configuration, and DB dependency `get_db()`.
- `app/models/`: Declarative ORM models (`user.py`, `closet.py`).
- `app/main.py`: Lifespan event handler executing safe startup schema updates.

## Guidelines & Rules

### 1. ORM Model Design
- Use `Base = declarative_base()` or `Base(DeclarativeBase)` with explicit `__tablename__`.
- Use primary keys (`id = Column(Integer, primary_key=True, index=True)`).
- Establish foreign keys clearly (`user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))`).
- Define `relationship(...)` with `back_populates` for bi-directional traversal.

### 2. Session Management
- Always use FastAPI `Depends(get_db)` to acquire a thread-local database session.
- Always `db.commit()` and `db.refresh(instance)` after inserting or updating models.
- Handle database exceptions cleanly; rollback transactions on failure:
  ```python
  try:
      db.add(new_item)
      db.commit()
      db.refresh(new_item)
  except Exception as e:
      db.rollback()
      logger.error(f"Failed to save item: {e}")
      raise HTTPException(status_code=500, detail="Lỗi lưu dữ liệu.")
  ```

### 3. Migration Safety
- Never perform `Base.metadata.drop_all()` in production code.
- Startup migrations in `lifespan` must use standard SQL checks (e.g. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
- Ensure defaults and nullable flags match model specifications.
