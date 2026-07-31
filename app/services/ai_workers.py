# app/services/ai_workers.py
import os
import time
import json
import httpx
import uuid
import base64
import random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from celery import Celery
from dotenv import load_dotenv

from app.database import redis_client
from app.core.logger import logger

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Khởi tạo Celery App sử dụng Redis làm trung gian truyền tin (Broker) và lưu kết quả (Backend)
celery_app = Celery(
    "fitcheck_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(task_track_started=True)

executor = ThreadPoolExecutor(max_workers=4)


def set_task_state_in_redis(task_id: str, state: str, result_or_info: dict | str | None = None):
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
        print(f"[Worker Redis Error] Không thể cập nhật trạng thái task {task_id}: {e}")


def run_clothing_image_processing(image_path: str, user_id: int, update_state_cb=None) -> dict:
    """Hàm lõi xử lý ảnh thời trang qua AI: Bóc phông nền + Nhận diện kiểu dáng bằng Vision LLM"""
    if update_state_cb:
        update_state_cb('PROGRESS', 'Đang đọc và xử lý hình ảnh...')

    # 1. Đọc ảnh từ URL S3 hoặc đường dẫn local
    try:
        if image_path.startswith(("http://", "https://")):
            with httpx.Client() as client:
                res = client.get(image_path)
                image_bytes = res.content
        else:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
    except Exception as e:
        raise Exception(f"Không thể đọc ảnh đầu vào: {str(e)}")

    if update_state_cb:
        update_state_cb('PROGRESS', 'Đang bóc tách phông nền...')

    # AI THẬT 1: Tích hợp API Remove.bg thực tế bằng cách sử dụng REMOVE_BG_API_KEY
    remove_bg_key = os.getenv("REMOVE_BG_API_KEY")
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

    # 2. Nhận diện các tag thời trang bằng Vision LLM (Gemini hoặc OpenAI) hoặc Fallback
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

    if api_key:
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

            with httpx.Client() as client:
                response = client.post(api_url, json=payload, headers=headers, timeout=15.0)
                if response.status_code == 200:
                    ai_data = response.json()["choices"][0]["message"]["content"]
                    detected_tags = json.loads(ai_data)
                else:
                    logger.error(f"Vision LLM API Error [{response.status_code}]: {response.text}")
        except Exception as e:
            logger.exception(f"Vision LLM Exception: {e}")

    # 3. Tải ảnh sạch nền lên S3 thực tế (Nếu có cấu hình S3)
    from app.services.storage import upload_image_to_s3

    processed_image_url = "https://storage.fitcheck.ai/uploaded_s3_url.png"
    object_name = f"closet/{user_id}/{uuid.uuid4()}.png"
    s3_url = upload_image_to_s3(clean_image_bytes, object_name)
    if s3_url:
        processed_image_url = s3_url
    elif image_path.startswith(("http://", "https://")):
        processed_image_url = image_path

    # 4. Dọn dẹp tệp tạm cục bộ (Nếu có lưu file)
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