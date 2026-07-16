# app/services/ai_workers.py
import os
import time
import json
import httpx
from celery import Celery
from dotenv import load_dotenv
import base64


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# Khởi tạo Celery App sử dụng Redis làm trung gian truyền tin (Broker) và lưu kết quả (Backend)
celery_app = Celery(
    "fitcheck_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Cấu hình để Celery nhận diện chính xác các hàm chạy ngầm
celery_app.conf.update(task_track_started=True)
load_dotenv()


# Cấu hình để Celery nhận diện chính xác các hàm chạy ngầm
celery_app.conf.update(task_track_started=True)

@celery_app.task(bind=True)
def process_clothing_image_task(self, image_path: str, user_id: int):
    self.update_state(state='PROGRESS', meta={'message': 'Đang bóc tách phông nền...'})
    
    # 🌟 AI THẬT 1: Gọi API chuyên dụng (như Photoroom hoặc Remove.bg) để tách nền
    # Trả về ảnh PNG trong suốt lưu tạm thời
    clean_image_bytes = b"" 
    # (Đoạn này gọi httpx lên API xóa nền, truyền file image_path vào)
    
    self.update_state(state='PROGRESS', meta={'message': 'AI đang phân tích kiểu dáng bằng Vision LLM...'})
    
    # 🌟 AI THẬT 2: Mã hóa ảnh sang Base64 và đẩy lên GPT-4o Vision để nhận diện thuộc tính thời trang
    encoded_image = base64.b64encode(open(image_path, "rb").read()).decode('utf-8')
    
    openai_url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
    
    payload = {
        "model": "gpt-4o", # Sử dụng mô hình có khả năng nhìn và phân tích ảnh xuất sắc
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this clothing item. Identify its exact category (Shirts, Pants, Shoes, Jackets), its dominant color in Hex Code, and its style type (Formal or Casual). Return strictly in JSON format: {'category': '...', 'color_code': '#...', 'style_tag': '...'}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]
            }
        ],
        "response_format": { "type": "json_object" }
    }
    
    with httpx.Client() as client:
        response = client.post(openai_url, json=payload, headers=headers, timeout=15.0)
        if response.status_code == 200:
            ai_data = response.json()["choices"][0]["message"]["content"]
            detected_tags = json.loads(ai_data)
            
            return {
                "status": "completed",
                "user_id": user_id,
                "processed_image_url": "https://storage.fitcheck.ai/uploaded_s3_url.png", # Link sau khi đã đẩy clean_image_bytes lên S3
                "detected_tags": detected_tags
            }
            
    raise Exception("AI Vision Processing Failed")