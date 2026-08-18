---
name: fastapi-backend-rules
description: Standard instructions and patterns for developing FastAPI endpoints, Pydantic schemas, dependency injection, and HTTP exception handling in FitCheck Backend.
---

# FastAPI Backend Development Guide

This skill provides guidelines for extending and maintaining the FastAPI backend layer in `fitcheck-backend`.

## Endpoint Design Patterns

### 1. Router Definition
All API routes should be grouped logically under `app/routers/` with standard prefixes and tags:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/resource", tags=["Resource Name"])
```

### 2. Dependency Injection & User Context
Always extract `user_id` safely from `current_user`:

```python
@router.get("/my-items", response_model=List[ResourceSchema])
def get_user_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = cast(int, current_user.id)
    items = db.query(ResourceModel).filter(ResourceModel.user_id == user_id).all()
    return items
```

### 3. Pydantic Schemas (`app/schemas/`)
- Define separate schemas for `Create`, `Update`, and `Response` objects.
- Set `from_attributes = True` inside `ConfigDict` or `Config` class for ORM compatibility.
- Add field validation using Pydantic `@field_validator` or `Field(...)` limits.

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional

class ItemBase(BaseModel):
    name: str
    category: str
    color_code: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
```

### 4. Consistent Error Responses
- Use standard HTTP status codes from `fastapi.status`.
- Return clear error detail strings in Vietnamese/English suitable for mobile frontend consumption.
- Handle database null results with `status.HTTP_444_NOT_FOUND` or `status.HTTP_400_BAD_REQUEST`.
