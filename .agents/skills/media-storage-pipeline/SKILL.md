---
name: media-storage-pipeline
description: Best practices for handling image uploads, AWS S3 object storage integration, MIME validation, image resizing, and file cleanup in FitCheck.
---

# Media Storage & Image Processing Pipeline Guide

This skill governs the handling, validation, storage, and processing of user-uploaded clothing photos and media assets in `fitcheck-backend`.

## Storage Architecture

- **Service Module**: `app/services/storage.py`
- **Supported Backends**: AWS S3 / MinIO / S3-compatible cloud buckets, with local disk storage fallback during development.
- **Image Processing**: Pillow (PIL) for image resizing, format normalization (JPEG/PNG/WEBP), and metadata extraction.

---

## Best Practices & Rules

### 1. Upload Validation
- Always validate MIME type (allow `image/jpeg`, `image/png`, `image/webp`).
- Enforce file size limits (e.g. max 10MB) before loading into memory.
- Generate secure, collision-free object keys (e.g., `uploads/{user_id}/{uuid4()}.webp`).

### 2. Image Optimization & Sanitization
- Strip dangerous EXIF metadata while retaining orientation if necessary.
- Optimize and compress high-resolution mobile camera uploads to prevent high bandwidth and storage costs.
- Store both the original/optimized image and a lightweight thumbnail for mobile feed rendering.

### 3. Asynchronous / S3 Operations
- Use non-blocking IO or execute synchronous S3 `boto3` calls via worker tasks or threadpools for large files.
- Generate pre-signed URLs with reasonable expiration times for private assets or serve via CDN.
- Clean up temporary local files (`temp_uploads/`) in `finally:` blocks.

```python
from app.services.storage import upload_file_to_s3
from fastapi import UploadFile, HTTPException

async def handle_user_upload(file: UploadFile, user_id: int) -> str:
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Định dạng ảnh không hợp lệ (hỗ trợ JPG, PNG, WEBP).")
    
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Kích thước ảnh vượt quá giới hạn 10MB.")
        
    image_url = upload_file_to_s3(file_bytes, filename=file.filename, user_id=user_id)
    return image_url
```
