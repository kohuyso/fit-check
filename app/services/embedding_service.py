# app/services/embedding_service.py
import json
import hashlib
import numpy as np
import httpx
from typing import List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.logger import logger
from app.db.session import redis_client
from app.models.closet import ClothingItem, EMBEDDING_DIM

def _generate_fallback_embedding(text_content: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Sinh vector giả lập xác định (Deterministic Pseudo-Embedding) dựa trên SHA256 khi không có API key.
    Đảm bảo cùng một chuỗi text sẽ luôn sinh ra cùng 1 vector chuẩn hóa L2, không làm sập hệ thống.
    """
    seed_int = int(hashlib.sha256(text_content.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.RandomState(seed_int)
    vec = rng.randn(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

async def get_text_embedding(text_content: str) -> List[float]:
    """
    Sinh vector embedding từ chuỗi văn bản sử dụng Gemini / OpenAI API (có áp dụng Redis Cache).
    Mặc định vector chuẩn 768 chiều (Gemini text-embedding-004).
    """
    clean_text = text_content.strip()
    if not clean_text:
        return [0.0] * EMBEDDING_DIM

    # 1. Kiểm tra Cache Redis
    text_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:16]
    cache_key = f"ai_cache:embedding:v1:{text_hash}"
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as cache_err:
        logger.warning(f"[Redis Cache Warning] Embedding get failed: {cache_err}")

    embedding_vector: Optional[List[float]] = None

    # 2. Gọi Gemini Embedding API nếu có API key
    gemini_key = settings.GEMINI_API_KEY
    if gemini_key and "your_" not in gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={gemini_key}"
            payload = {
                "model": "models/gemini-embedding-001",
                "content": {
                    "parts": [{"text": clean_text}]
                },
                "outputDimensionality": EMBEDDING_DIM
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if len(values) == EMBEDDING_DIM:
                        embedding_vector = values
                else:
                    logger.warning(f"Gemini Embedding HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as api_err:
            logger.warning(f"Gemini Embedding call failed: {api_err}")

    # 3. Gọi OpenAI Embedding nếu cấu hình
    if not embedding_vector and settings.OPENAI_API_KEY and "your_" not in settings.OPENAI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={
                        "model": "text-embedding-3-small",
                        "input": clean_text,
                        "dimensions": EMBEDDING_DIM
                    }
                )
                if resp.status_code == 200:
                    embedding_vector = resp.json()["data"][0]["embedding"]
        except Exception as oai_err:
            logger.warning(f"OpenAI Embedding call failed: {oai_err}")

    # 4. Fallback Deterministic Vector nếu không có API ngoài
    if not embedding_vector:
        embedding_vector = _generate_fallback_embedding(clean_text, EMBEDDING_DIM)

    # 5. Lưu Cache Redis (1 tuần)
    try:
        redis_client.setex(cache_key, 604800, json.dumps(embedding_vector))
    except Exception as cache_err:
        logger.warning(f"[Redis Cache Warning] Embedding setex failed: {cache_err}")

    return embedding_vector

def compute_and_save_item_embedding(db: Session, item: ClothingItem) -> Optional[List[float]]:
    """
    Sinh và cập nhật vector embedding đồng bộ vào Database cho 1 món đồ cụ thể.
    """
    try:
        search_text = item.build_searchable_text()
        
        # Đồng bộ qua helper deterministic hoặc call API
        # Đối với sync workflow (worker / router):
        text_hash = hashlib.sha256(search_text.encode("utf-8")).hexdigest()[:16]
        cache_key = f"ai_cache:embedding:v1:{text_hash}"
        
        cached = None
        try:
            cached = redis_client.get(cache_key)
        except Exception:
            pass

        if cached:
            vec = json.loads(cached)
        else:
            gemini_key = settings.GEMINI_API_KEY
            vec = None
            if gemini_key and "your_" not in gemini_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={gemini_key}"
                    with httpx.Client(timeout=8.0) as client:
                        resp = client.post(url, json={
                            "model": "models/gemini-embedding-001",
                            "content": {"parts": [{"text": search_text}]},
                            "outputDimensionality": EMBEDDING_DIM
                        })
                        if resp.status_code == 200:
                            vec = resp.json().get("embedding", {}).get("values", [])
                except Exception:
                    vec = None
            
            if not vec or len(vec) != EMBEDDING_DIM:
                vec = _generate_fallback_embedding(search_text, EMBEDDING_DIM)

            try:
                redis_client.setex(cache_key, 604800, json.dumps(vec))
            except Exception:
                pass

        item.embedding = vec
        db.commit()
        return vec
    except Exception as e:
        logger.error(f"Lỗi khi tính toán embedding cho ClothingItem id={item.id}: {e}")
        db.rollback()
        return None

async def search_wardrobe_hybrid(
    db: Session,
    user_id: int,
    query_text: str,
    categories: Optional[List[str]] = None,
    exclude_item_ids: Optional[List[int]] = None,
    top_k: int = 6
) -> List[ClothingItem]:
    """
    🌟 Hybrid Semantic Search:
    1. SQL Filter: Lọc đúng user_id, danh mục quần áo (nếu có), loại trừ các món đã chọn.
    2. Vector Semantic Ranking: Xếp hạng độ tương đồng Cosine (Cosine Distance <=>) dựa trên query_vector.
    3. Giới hạn Top K kết quả phù hợp nhất thay vì lôi toàn bộ tủ đồ lên RAM.
    """
    try:
        # 1. Sinh vector cho câu query
        query_vector = await get_text_embedding(query_text)
        
        # 2. Xây dựng truy vấn Hybrid trên SQLAlchemy
        query = db.query(ClothingItem).filter(
            ClothingItem.user_id == user_id,
            ClothingItem.embedding.isnot(None)
        )

        if categories:
            query = query.filter(ClothingItem.category.in_(categories))

        if exclude_item_ids:
            query = query.filter(~ClothingItem.id.in_(exclude_item_ids))

        # Sắp xếp theo khoảng cách Cosine nhỏ nhất
        query = query.order_by(ClothingItem.embedding.cosine_distance(query_vector))
        items = query.limit(top_k).all()

        # Fallback an toàn: Nếu user chưa có item nào được embed, lấy theo SQL thông thường
        if not items:
            fb_query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
            if categories:
                fb_query = fb_query.filter(ClothingItem.category.in_(categories))
            if exclude_item_ids:
                fb_query = fb_query.filter(~ClothingItem.id.in_(exclude_item_ids))
        return items
    except Exception as e:
        logger.error(f"[Hybrid Search Error]: {e}")
        fb_query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
        if categories:
            fb_query = fb_query.filter(ClothingItem.category.in_(categories))
        return fb_query.limit(top_k).all()

def get_text_embedding_sync(text_content: str) -> List[float]:
    """
    Phiên bản đồng bộ của get_text_embedding phục vụ các LangGraph Tools / Celery Tasks
    """
    clean_text = text_content.strip()
    if not clean_text:
        return [0.0] * EMBEDDING_DIM

    text_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:16]
    cache_key = f"ai_cache:embedding:v1:{text_hash}"
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    gemini_key = settings.GEMINI_API_KEY
    embedding_vector = None

    if gemini_key and "your_" not in gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={gemini_key}"
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, json={
                    "model": "models/gemini-embedding-001",
                    "content": {"parts": [{"text": clean_text}]},
                    "outputDimensionality": EMBEDDING_DIM
                })
                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if len(values) == EMBEDDING_DIM:
                        embedding_vector = values
        except Exception as e:
            logger.warning(f"Sync Gemini Embedding call failed: {e}")

    if not embedding_vector:
        embedding_vector = _generate_fallback_embedding(clean_text, EMBEDDING_DIM)

    try:
        redis_client.setex(cache_key, 604800, json.dumps(embedding_vector))
    except Exception:
        pass

    return embedding_vector

def search_wardrobe_hybrid_sync(
    db: Session,
    user_id: int,
    query_text: str,
    categories: Optional[List[str]] = None,
    exclude_item_ids: Optional[List[int]] = None,
    top_k: int = 6
) -> List[ClothingItem]:
    """
    Phiên bản đồng bộ của Hybrid Search phục vụ LangGraph Tool Execution
    """
    try:
        query_vector = get_text_embedding_sync(query_text)
        query = db.query(ClothingItem).filter(
            ClothingItem.user_id == user_id,
            ClothingItem.embedding.isnot(None)
        )

        if categories:
            query = query.filter(ClothingItem.category.in_(categories))

        if exclude_item_ids:
            query = query.filter(~ClothingItem.id.in_(exclude_item_ids))

        query = query.order_by(ClothingItem.embedding.cosine_distance(query_vector))
        items = query.limit(top_k).all()

        if not items:
            fb_query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
            if categories:
                fb_query = fb_query.filter(ClothingItem.category.in_(categories))
            if exclude_item_ids:
                fb_query = fb_query.filter(~ClothingItem.id.in_(exclude_item_ids))
            items = fb_query.limit(top_k).all()

        return items
    except Exception as e:
        logger.error(f"[Hybrid Search Sync Error]: {e}")
        fb_query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
        if categories:
            fb_query = fb_query.filter(ClothingItem.category.in_(categories))
        return fb_query.limit(top_k).all()
