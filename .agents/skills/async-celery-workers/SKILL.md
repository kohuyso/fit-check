---
name: async-celery-workers
description: Guidelines for managing Celery tasks, Redis queues, background asynchronous job execution, and worker error handling in FitCheck.
---

# Celery & Background Workers Guide

This skill governs the asynchronous processing architecture, Celery worker task definitions, and Redis message queue management for `fitcheck-backend`.

## Architecture Overview

Heavy or high-latency operations must NOT block the FastAPI request-response loop. These must be dispatched to background workers:
- Multimodal AI item categorization and tagging.
- Complex batch outfit matrix generation.
- Image processing, thumbnail generation, and remote S3 synchronization.

Primary module: `app/services/ai_workers.py`

---

## Best Practices & Patterns

### 1. Task Definition & Serialization
- Decorate Celery tasks with `@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)`.
- Pass simple scalar primitives (e.g. `item_id: int`, `user_id: int`) instead of complex ORM model instances.
- Open a dedicated `SessionLocal()` within the worker task and guarantee cleanup with a `finally: db.close()` block.

```python
from app.services.ai_workers import celery_app
from app.database import SessionLocal
from app.core.logger import logger

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_clothing_item_ai(self, item_id: int):
    db = SessionLocal()
    try:
        # Perform AI operations and database updates
        logger.info(f"Processing AI classification for item_id={item_id}")
        ...
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Worker error processing item {item_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()
```

### 2. Task Dispatching from Routers
- Enqueue tasks cleanly from FastAPI route handlers using `.delay()` or `.apply_async()`.
- Return immediate acknowledgment (e.g., `202 Accepted` or initial entity with `ai_status="processing"`).

```python
# In router:
new_item = closet_service.create_item(db, item_in, user_id=current_user.id)
process_clothing_item_ai.delay(new_item.id)
return new_item
```

### 3. Monitoring & Error Recovery
- Always record task progress / status in database flags (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
- Provide fallback values if AI processing continuously fails so user data is never stuck in a zombie state.
