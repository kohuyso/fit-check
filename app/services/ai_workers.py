import os
import json
import httpx
import uuid
import base64
import random
import hashlib
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from celery import Celery

from app.core.config import settings
from app.database import redis_client
from app.core.logger import logger

# Khởi tạo Celery App sử dụng Redis từ Settings
redis_url = settings.REDIS_URL or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery(
    "fitcheck_tasks",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.update(task_track_started=True)

executor = ThreadPoolExecutor(max_workers=4)

def set_task_state_in_redis(task_id: str, state: str, result_or_info: Optional[Any] = None) -> None:
    """Ghi trạng thái task trực tiếp vào Redis theo đúng cấu trúc Celery AsyncResult"""
    try:
        if state == "FAILURE":
            err_msg = result_or_info.get("error", result_or_info) if isinstance(result_or_info, dict) else str(result_or_info)
            res_payload = {
                "exc_type": "Exception",
                "exc_message": [str(err_msg)],
                "exc_module": "builtins"
            }
        else:
            res_payload = result_or_info

        meta = {
            "status": state,
            "result": res_payload,
            "traceback": None,
            "children": [],
            "date_done": datetime.now(timezone.utc).isoformat() if state in ("SUCCESS", "FAILURE") else None,
            "task_id": task_id
        }
        redis_client.setex(f"celery-task-meta-{task_id}", 86400, json.dumps(meta))
    except Exception as e:
        logger.error(f"[Worker Redis Error] Không thể cập nhật trạng thái task {task_id}: {e}")

def run_clothing_image_processing(image_path: str, user_id: int, update_state_cb: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
    """Hàm lõi xử lý ảnh thời trang qua AI: Bóc phông nền + Nhận diện kiểu dáng bằng Vision LLM"""
    if update_state_cb:
        update_state_cb('PROGRESS', 'Đang đọc và xử lý hình ảnh...')

    image_bytes: bytes = b""
    try:
        if image_path.startswith(("http://", "https://")):
            fetched_s3 = False
            if ".s3." in image_path or ".amazonaws.com" in image_path:
                try:
                    import boto3
                    access_key = settings.AWS_ACCESS_KEY_ID
                    secret_key = settings.AWS_SECRET_ACCESS_KEY
                    region = settings.AWS_REGION
                    if ".s3.amazonaws.com/" in image_path:
                        parts = image_path.split(".s3.amazonaws.com/")
                        bucket_name = parts[0].split("//")[-1]
                        key = parts[1].split('?')[0]
                        s3_client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
                        obj = s3_client.get_object(Bucket=bucket_name, Key=key)
                        image_bytes = obj['Body'].read()
                        fetched_s3 = True
                except Exception as s3_err:
                    logger.warning(f"boto3 S3 download failed ({s3_err}), falling back to HTTP GET")

            if not fetched_s3:
                with httpx.Client() as client:
                    res = client.get(image_path)
                    if res.status_code != 200:
                        raise Exception(f"HTTP GET {image_path} failed status {res.status_code}")
                    if res.content.strip().startswith(b"<?xml") or b"<Error>" in res.content[:100]:
                        raise Exception(f"S3 returned XML error response instead of image: {res.text[:200]}")
                    image_bytes = res.content
        else:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
    except Exception as e:
        raise Exception(f"Không thể đọc ảnh đầu vào: {str(e)}")

    if update_state_cb:
        update_state_cb('PROGRESS', 'Đang bóc tách phông nền...')

    remove_bg_key = settings.REMOVE_BG_API_KEY
    clean_image_bytes = image_bytes
    if remove_bg_key and "your_" not in remove_bg_key:
        try:
            with httpx.Client() as client:
                res = client.post(
                    "https://api.remove.bg/v1.0/removebg",
                    headers={"X-Api-Key": remove_bg_key},
                    files={"image_file": image_bytes},
                    data={"size": "auto"},
                    timeout=20.0
                )
                if res.status_code == 200:
                    clean_image_bytes = res.content
                else:
                    logger.error(f"Remove.bg API Error [{res.status_code}]: {res.text}")
        except Exception as e:
            logger.exception(f"Remove.bg Exception: {e}")

    if update_state_cb:
        update_state_cb('PROGRESS', 'AI đang phân tích kiểu dáng bằng Vision LLM...')

    from app.services.ai_engine import get_ai_config
    api_key, api_url, _, vision_model = get_ai_config()

    filename = os.path.basename(image_path).lower()
    fallback_category = "Shirts"
    if any(w in filename for w in ["pant", "trouser", "jean", "quan", "slack"]):
        fallback_category = "Pants"
    elif any(w in filename for w in ["shoe", "sneaker", "boot", "giay", "footwear"]):
        fallback_category = "Shoes"
    elif any(w in filename for w in ["jacket", "coat", "hoodie", "ao-khoac", "blazer"]):
        fallback_category = "Jackets"

    colors = ["#1E293B", "#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#FFFFFF", "#000000"]
    fallback_color = random.choice(colors)
    fallback_style = random.choice(["Formal", "Casual"])

    detected_tags = {
        "category": fallback_category,
        "color_code": fallback_color,
        "style_tag": fallback_style
    }

    image_hash = hashlib.sha256(clean_image_bytes).hexdigest()
    cache_key = f"ai_cache:image_tagging:{image_hash}"
    cache_hit = False

    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            detected_tags = json.loads(cached_data)
            logger.info(f"[Redis Cache HIT] Vision LLM tagging skipped for image_hash={image_hash[:10]}")
            cache_hit = True
    except Exception as cache_err:
        logger.warning(f"[Redis Cache Error] Vision LLM cache get failed: {cache_err}")

    if not cache_hit and api_key:
        try:
            mime_type = "image/jpeg"
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"
            encoded_image = base64.b64encode(clean_image_bytes).decode('utf-8')
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this clothing item. Identify its exact category (Shirts, Pants, Shoes, Jackets), its dominant color in Hex Code, and its style type (Formal or Casual). Return strictly in JSON format: {'category': '...', 'color_code': '#...', 'style_tag': '...'}"},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}}
                        ]
                    }
                ],
                "response_format": { "type": "json_object" }
            }

            timeout_cfg = httpx.Timeout(settings.AI_REQUEST_TIMEOUT, connect=10.0)
            with httpx.Client(timeout=timeout_cfg) as client:
                response = client.post(api_url, json=payload, headers=headers)
                if response.status_code == 200:
                    ai_data = response.json()["choices"][0]["message"]["content"]
                    detected_tags = json.loads(ai_data)
                    try:
                        redis_client.setex(cache_key, 864000, json.dumps(detected_tags, ensure_ascii=False))
                    except Exception as cache_err:
                        logger.warning(f"[Redis Cache Error] Vision LLM cache setex failed: {cache_err}")
                else:
                    logger.error(f"Vision LLM API Error [{response.status_code}]: {response.text}")
        except httpx.TimeoutException as te:
            logger.warning(f"Vision LLM API Timeout ({settings.AI_REQUEST_TIMEOUT}s): {te}. Using fallback clothing tags.")
        except Exception as e:
            logger.exception(f"Vision LLM Exception: {e}")

    from app.services.storage import upload_image_to_s3

    processed_image_url = "https://storage.fitcheck.ai/uploaded_s3_url.png"
    object_name = f"closet/{user_id}/{uuid.uuid4()}.png"
    s3_url = upload_image_to_s3(clean_image_bytes, object_name)
    if s3_url:
        processed_image_url = s3_url
    elif image_path.startswith(("http://", "https://")):
        processed_image_url = image_path

    if not image_path.startswith(("http://", "https://")):
        try:
            os.remove(image_path)
        except OSError:
            pass

    return {
        "status": "completed",
        "user_id": user_id,
        "processed_image_url": processed_image_url,
        "detected_tags": detected_tags
    }

@celery_app.task(bind=True)
def process_clothing_image_task(self, image_path: str, user_id: int):
    def update_cb(state: str, message: str):
        self.update_state(state=state, meta={'message': message})
    return run_clothing_image_processing(image_path, user_id, update_state_cb=update_cb)

def dispatch_scan_task(image_path: str, user_id: int) -> str:
    """Tạo task quét ảnh: Ưu tiên Celery Worker nếu đang chạy, ngược lại fallback sang Background ThreadPool"""
    task_id = str(uuid.uuid4())

    worker_active = False
    try:
        inspect = celery_app.control.inspect(timeout=0.3)
        active_workers = inspect.active()
        if active_workers:
            worker_active = True
    except Exception:
        worker_active = False

    if worker_active:
        process_clothing_image_task.apply_async(args=[image_path, user_id], task_id=task_id)
    else:
        def bg_worker():
            set_task_state_in_redis(task_id, 'PROGRESS', {'message': 'Đang đọc và xử lý hình ảnh...'})
            def update_cb(state: str, message: str):
                set_task_state_in_redis(task_id, state, {'message': message})
            try:
                res = run_clothing_image_processing(image_path, user_id, update_state_cb=update_cb)
                set_task_state_in_redis(task_id, 'SUCCESS', res)
            except Exception as err:
                set_task_state_in_redis(task_id, 'FAILURE', {'error': str(err)})

        executor.submit(bg_worker)

    return task_id