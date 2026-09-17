from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.closet import ClothingItem
from app.schemas import closet_schema
from app.services.color_math import get_color_name_from_hex

router = APIRouter()

@router.get("/trends", response_model=closet_schema.ExploreTrendsResponse)
def get_fashion_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Khám phá Xu hướng thời trang được cá nhân hóa dựa trên dữ liệu tủ đồ người dùng.
    """
    user_items = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id).all()
    user_styles = list(set([i.style_tag for i in user_items if i.style_tag]))
    primary_style = user_styles[0] if user_styles else "Smart Casual"

    season_lookbooks = [
        {
            "id": 1,
            "title": f"Lookbook {primary_style} 2026",
            "subtitle": f"Bộ sưu tập tối ưu riêng cho tủ đồ {len(user_items)} món của bạn",
            "banner_url": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800",
            "featured_items_count": len(user_items),
            "tags": [primary_style, "Personalized", "AI Curated"]
        },
        {
            "id": 2,
            "title": "Urban Executive Smart Casual",
            "subtitle": "Giải pháp phối đồ linh hoạt từ công sở ra phố",
            "banner_url": "https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?w=800",
            "featured_items_count": 6,
            "tags": ["Smart Casual", "Workwear", "Layering"]
        }
    ]

    trend_articles = [
        {
            "id": 101,
            "title": f"Quy tắc phối đồ {primary_style} chuẩn phong cách cá nhân",
            "season": "Summer 2026",
            "read_time": "3 min read",
            "image_url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800",
            "content": f"Dựa trên phân tích tủ đồ, phong cách chủ đạo của bạn là {primary_style}. Việc kết hợp linh hoạt các chất liệu nhẹ như Linen hay Denim sẽ giúp bạn giữ nét thời thượng bất kể thời tiết.",
            "tags": [primary_style, "Layering", "AI Tips"]
        },
        {
            "id": 102,
            "title": "Xu hướng Color Blocking Tương phản dịu cho năm nay",
            "season": "All Season",
            "read_time": "5 min read",
            "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800",
            "content": "Thay vì kết hợp các màu chói rực rỡ, xu hướng năm nay hướng tới tông pastel tương phản nhẹ như Navy Blue - Off White hoặc Beige - Olive Green.",
            "tags": ["Color Matching", "Trends"]
        }
    ]

    return {
        "season_lookbooks": season_lookbooks,
        "trend_articles": trend_articles
    }

@router.get("/color-theory", response_model=closet_schema.ColorTheoryResponse)
def get_color_theory_guides(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Hướng dẫn Lý thuyết Phối màu cá nhân hóa dựa theo các item thực tế trong tủ đồ.
    """
    user_items = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id).all()
    
    shirts = [i for i in user_items if i.category.lower() in ("shirts", "shirt")]
    pants = [i for i in user_items if i.category.lower() in ("pants", "pant")]
    shoes = [i for i in user_items if i.category.lower() in ("shoes", "shoe")]

    top_name = f"{get_color_name_from_hex(str(shirts[0].color_code))} Shirt" if shirts else "Navy Blue Shirt"
    bottom_name = f"{get_color_name_from_hex(str(pants[0].color_code))} Pants" if pants else "Dark Chinos"
    shoe_name = f"{get_color_name_from_hex(str(shoes[0].color_code))} Shoes" if shoes else "Leather Sneakers"

    guides = [
        {
            "harmony_type": "Monochromatic (Phối màu Đơn sắc)",
            "description": "Sử dụng các sắc thái (shades) khác nhau của cùng 1 tông màu chính.",
            "color_wheel_tip": "Tăng tính thanh lịch và tạo cảm giác chiều cao tốt hơn.",
            "recommended_combinations": [
                {"top": top_name, "bottom": bottom_name, "shoes": shoe_name}
            ]
        },
        {
            "harmony_type": "Complementary (Phối màu Tương phản)",
            "description": "Kết hợp 2 màu nằm đối diện nhau trên Bánh xe màu sắc.",
            "color_wheel_tip": "Tạo điểm nhấn thị giác mạnh mẽ nhưng vẫn hài hòa.",
            "recommended_combinations": [
                {"top": top_name, "bottom": "Camel Chinos", "shoes": "Brown Boots"}
            ]
        },
        {
            "harmony_type": "Analogous (Phối màu Tương đồng)",
            "description": "Kết hợp 3 màu nằm liền kề nhau trên bánh xe màu sắc.",
            "color_wheel_tip": "Mang lại vẻ ngoài tự nhiên, dịu mắt và thanh thoát.",
            "recommended_combinations": [
                {"top": "Sky Blue Shirt", "bottom": bottom_name, "shoes": shoe_name}
            ]
        },
        {
            "harmony_type": "Triadic (Phối màu Tam giác cân)",
            "description": "Kết hợp 3 màu tạo thành tam giác đều trên bánh xe màu sắc.",
            "color_wheel_tip": "Cân bằng năng động và nổi bật cho các bộ trang phục dạo phố.",
            "recommended_combinations": [
                {"top": top_name, "bottom": bottom_name, "shoes": shoe_name}
            ]
        }
    ]

    ai_advice = f"Mẹo từ AI Stylist: Tủ đồ của bạn có {len(user_items)} món. Hãy áp dụng quy tắc 60-30-10 (60% màu chủ đạo, 30% màu bổ trợ, 10% màu điểm nhấn) để phối đồ tối ưu nhất."

    return {
        "guides": guides,
        "ai_advice": ai_advice
    }

@router.get("/trends/{article_id}", response_model=closet_schema.TrendArticle)
def get_trend_article_detail(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy thông tin chi tiết của một bài viết xu hướng thời trang"""
    trends_response = get_fashion_trends(db=db, current_user=current_user)
    articles = trends_response.get("trend_articles", [])
    for article in articles:
        if article.get("id") == article_id:
            return article

    return {
        "id": article_id,
        "title": "Xu hướng phối đồ Thông minh 2026",
        "season": "All Season",
        "read_time": "4 min read",
        "image_url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800",
        "content": "Phối đồ tối giản kết hợp với các item đa năng sẽ là xu hướng thống trị trong năm 2026.",
        "tags": ["Smart Casual", "AI Styling"]
    }
