from typing import List, Dict, Any, Optional, Tuple, cast
from sqlalchemy.orm import Session
from app.models.closet import ClothingItem, OutfitCombo
from app.services.color_math import get_color_name_from_hex
from app.core.logger import logger

# ============================================================================
# 👗 ENHANCED CATEGORY GROUPS & VALIDATION TAXONOMY
# ============================================================================

CATEGORY_GROUPS: Dict[str, set] = {
    "tops": {
        "shirts", "shirt", "t-shirts", "t-shirt", "tshirts", "tshirt", "tops", "top",
        "blouses", "blouse", "sweaters", "sweater", "hoodies", "hoodie", "polos", "polo",
        "tank tops", "tank top", "tanktops", "crop tops", "crop top", "flannels", "flannel",
        "vests", "vest", "sweatshirts", "sweatshirt", "cardigan tops", "knitwear",
        # Hỗ trợ tiếng Việt
        "ao", "ao thun", "ao so mi", "ao len", "ao ba lo", "ao phong", "ao polo", "ao croptop"
    },
    "bottoms": {
        "pants", "pant", "jeans", "jean", "shorts", "short", "skirts", "skirt",
        "trousers", "trouser", "joggers", "jogger", "sweatpants", "sweatpant",
        "leggings", "legging", "chinos", "chino", "cargo pants", "cargo", "culottes",
        "bermuda", "khakis", "khaki",
        # Hỗ trợ tiếng Việt
        "quan", "quan jean", "quan tay", "quan dui", "quan short", "chan vay", "vay ngan",
        "quan jogger", "quan ong rong", "quan kaki"
    },
    "one_piece": {
        "dresses", "dress", "jumpsuits", "jumpsuit", "rompers", "romper",
        "overalls", "overall", "gowns", "gown", "maxi dresses", "maxi dress",
        "sundresses", "sundress", "suits", "suit",
        # Hỗ trợ tiếng Việt
        "ao dai", "ao dai cach tan", "dam", "dam da hoi", "dam suong", "vay lien",
        "set do bo", "jumpsuit nu"
    },
    "outerwear": {
        "jackets", "jacket", "coats", "coat", "blazers", "blazer", "trench coats",
        "trench coat", "windbreakers", "windbreaker", "parkas", "parka", "bombers",
        "bomber", "puffer jackets", "puffer jacket", "puffers", "cardigans", "cardigan",
        "overcoats", "overcoat", "denim jackets", "leather jackets", "vest outerwear",
        # Hỗ trợ tiếng Việt
        "ao khoac", "ao vest", "ao blazer", "ao gio", "ao phao", "ao da", "ao khoac gio"
    },
    "shoes": {
        "shoes", "shoe", "sneakers", "sneaker", "boots", "boot", "loafers", "loafer",
        "sandals", "sandal", "heels", "heel", "flats", "flat", "mules", "mule",
        "oxfords", "oxford", "slippers", "slipper", "derbies", "derby", "espadrilles",
        # Hỗ trợ tiếng Việt
        "giay", "giay the thao", "giay sneaker", "giay cao got", "giay luoi", "giay da",
        "dep", "guoc", "dep quai hau", "giay sandal"
    },
    "accessories": {
        "bags", "bag", "backpacks", "backpack", "handbags", "handbag", "crossbody",
        "crossbody bags", "tote bags", "totes", "clutches", "clutch", "hats", "hat",
        "caps", "cap", "beanies", "beanie", "belts", "belt", "scarves", "scarf",
        "sunglasses", "glasses", "jewelry", "watches", "watch", "ties", "tie",
        "bowties", "socks", "wallets", "accessories",
        # Hỗ trợ tiếng Việt
        "tui", "tui xach", "balo", "that lung", "day nit", "mu", "non", "mu luoi trai",
        "khan choang", "kinh", "kinh ram", "dong ho", "ca vat", "phu kien"
    }
}

import unicodedata
import re

def _normalize_text(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu về không dấu để so khớp linh hoạt"""
    norm = unicodedata.normalize('NFD', text)
    norm = re.sub(r'[\u0300-\u036f]', '', norm)
    return norm.replace('đ', 'd').replace('Đ', 'D').strip().lower()

def get_category_group(category: Optional[str]) -> str:
    """Xác định nhóm phân loại trang phục chuẩn dựa trên chuỗi category (hỗ trợ cả tiếng Anh lẫn tiếng Việt)"""
    if not category:
        return "other"
    
    raw_cat = category.strip().lower()
    unaccented_cat = _normalize_text(raw_cat)
    
    # 1. Khớp chính xác trong từ điển (cả có dấu và không dấu)
    for group, synonyms in CATEGORY_GROUPS.items():
        if raw_cat in synonyms or unaccented_cat in synonyms:
            return group
            
    # 2. Khớp chuỗi con heuristic
    for group, synonyms in CATEGORY_GROUPS.items():
        for syn in synonyms:
            norm_syn = _normalize_text(syn)
            if len(norm_syn) >= 3 and (norm_syn in unaccented_cat or unaccented_cat in norm_syn):
                return group

    return "other"

def validate_outfit_category_composition(items: List[ClothingItem]) -> Tuple[bool, Optional[str]]:
    """
    🛡️ Deterministic Guardrail: Kiểm tra tính hợp lý & cấu trúc thời trang của set đồ.
    Trả về (True, None) nếu hợp lệ, hoặc (False, error_message) để kích hoạt Self-Correction Loop.
    """
    if not items or len(items) < 2:
        return False, "Cần tối thiểu 2 món đồ để tạo thành một bộ outfit hoàn chỉnh."

    grouped_items: Dict[str, List[ClothingItem]] = {
        "tops": [],
        "bottoms": [],
        "one_piece": [],
        "outerwear": [],
        "shoes": [],
        "accessories": [],
        "other": []
    }

    for item in items:
        group = get_category_group(item.category)
        grouped_items[group].append(item)

    # 1. 🚫 Xung đột: Nhiều hơn 1 Quần / Váy (Bottoms)
    if len(grouped_items["bottoms"]) > 1:
        bottom_descriptions = [f"ID {i.id} ({i.color_name or ''} {i.category})".strip() for i in grouped_items["bottoms"]]
        return False, (
            f"Xung đột phân loại: Không thể chọn nhiều hơn 1 Quần/Chân váy trong cùng một set đồ "
            f"(đang chọn: {', '.join(bottom_descriptions)}). "
            f"Vui lòng chỉ giữ 1 Quần/Váy và dùng tool search_closet_rag để chọn thêm 1 Áo hoặc Áo khoác!"
        )

    # 2. 🚫 Xung đột: Nhiều hơn 1 Đầm / Váy liền (One-piece)
    if len(grouped_items["one_piece"]) > 1:
        one_piece_descriptions = [f"ID {i.id} ({i.color_name or ''} {i.category})".strip() for i in grouped_items["one_piece"]]
        return False, (
            f"Xung đột phân loại: Không thể chọn nhiều hơn 1 Đầm/Váy liền trong cùng một set đồ "
            f"(đang chọn: {', '.join(one_piece_descriptions)}). "
            f"Vui lòng chọn 1 Đầm và phối cùng Áo khoác, Giày hoặc Phụ kiện!"
        )

    # 3. 🚫 Xung đột: Đầm liền (One-piece) + Quần / Chân váy (Bottoms)
    if grouped_items["one_piece"] and grouped_items["bottoms"]:
        one_piece_desc = f"ID {grouped_items['one_piece'][0].id} ({grouped_items['one_piece'][0].category})"
        bottom_desc = f"ID {grouped_items['bottoms'][0].id} ({grouped_items['bottoms'][0].category})"
        return False, (
            f"Xung đột phân loại: Đã chọn Đầm liền/Váy liền ({one_piece_desc}) thì không thể phối kèm Quần/Chân váy ({bottom_desc}). "
            f"Vui lòng bỏ món Quần và phối Đầm cùng Áo khoác (Jackets), Giày (Shoes) hoặc Phụ kiện (Accessories)!"
        )

    # 4. 🚫 Xung đột: Nhiều hơn 1 đôi Giày (Shoes)
    if len(grouped_items["shoes"]) > 1:
        shoes_descriptions = [f"ID {i.id} ({i.category})" for i in grouped_items["shoes"]]
        return False, (
            f"Xung đột phân loại: Không thể chọn nhiều hơn 1 đôi Giày trong cùng một set đồ "
            f"(đang chọn: {', '.join(shoes_descriptions)}). Hãy giữ đúng 1 đôi giày phù hợp nhất!"
        )

    # 5. 🚫 Xung đột: Quá nhiều áo trong (Tops) không có áo khoác (> 2 Tops)
    if len(grouped_items["tops"]) > 2:
        top_descriptions = [f"ID {i.id} ({i.category})" for i in grouped_items["tops"]]
        return False, (
            f"Xung đột phân loại: Chọn quá nhiều áo trong ({', '.join(top_descriptions)}). "
            f"Chỉ nên chọn tối đa 1 Áo trong (hoặc 1 Áo thun + 1 Áo sơ mi khoác nhẹ) và 1 Quần!"
        )

    # 6. 🛡️ Tính hoàn thiện cốt lõi (Core Outfit Completeness)
    has_one_piece = len(grouped_items["one_piece"]) >= 1
    has_top = len(grouped_items["tops"]) >= 1
    has_bottom = len(grouped_items["bottoms"]) >= 1
    has_outerwear = len(grouped_items["outerwear"]) >= 1

    if not has_one_piece:
        if has_top and not has_bottom:
            return False, (
                "Thiếu thành phần cốt lõi: Set đồ chỉ có Áo mà đang thiếu Quần/Chân váy. "
                "Vui lòng dùng tool `search_closet_rag` với category='Pants' hoặc 'Skirts' để tìm thêm 1 món Quần/Váy phù hợp!"
            )
        if has_bottom and not has_top:
            return False, (
                "Thiếu thành phần cốt lõi: Set đồ chỉ có Quần/Váy mà đang thiếu Áo. "
                "Vui lòng dùng tool `search_closet_rag` với category='Shirts' hoặc 'T-Shirts' để tìm thêm 1 món Áo phù hợp!"
            )
        if not (has_top and has_bottom) and not (has_outerwear and (has_top or has_bottom)):
            return False, (
                "Thiếu thành phần cốt lõi: Một set đồ hoàn chỉnh bắt buộc phải có đủ bộ "
                "(1 Áo + 1 Quần/Váy) HOẶC (1 Đầm liền/Jumpsuit)."
            )

    return True, None

def get_or_create_outfit_combo(
    db: Session,
    user_id: int,
    style_type: str,
    item_ids: List[int],
    validate_composition: bool = True
) -> Optional[OutfitCombo]:
    """
    Tìm hoặc tạo mới một OutfitCombo với cơ chế Guardrail:
    1. Lọc và loại bỏ các ID trùng lặp hoặc không hợp lệ.
    2. Xác thực quyền sở hữu: Tất cả items phải thuộc về user_id trong Database.
    3. Tránh tạo outfit nếu số món đồ hợp lệ < 2.
    4. Kiểm tra xung đột & cấu trúc thời trang (validate_outfit_category_composition).
    5. Tránh tạo trùng lặp bộ đồ giống nhau trong DB.
    """
    if not item_ids:
        return None

    # Chuyển đổi và lọc các ID hợp lệ
    clean_ids: List[int] = []
    for raw_id in item_ids:
        try:
            parsed_id = int(raw_id)
            if parsed_id not in clean_ids:
                clean_ids.append(parsed_id)
        except (ValueError, TypeError):
            continue

    if len(clean_ids) < 2:
        return None

    # Lấy các món đồ thực sự thuộc quyền sở hữu của user_id
    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id.in_(clean_ids)
    ).all()

    if len(items) < 2:
        return None

    # Kiểm tra tính hợp lệ về mặt danh mục trang phục
    if validate_composition:
        is_valid, validation_err = validate_outfit_category_composition(items)
        if not is_valid:
            logger.warning(f"[Guardrail Blocked Outfit Creation]: {validation_err}")
            return None

    valid_item_ids = [item.id for item in items]

    # Kiểm tra xem combo với đúng tập item_ids này đã tồn tại chưa
    combos = db.query(OutfitCombo).filter(OutfitCombo.user_id == user_id).all()
    for combo in combos:
        existing_ids = [item.id for item in combo.items]
        if sorted(existing_ids) == sorted(valid_item_ids):
            return combo

    new_combo = OutfitCombo(user_id=user_id, style_type=style_type, items=items)
    db.add(new_combo)
    db.commit()
    db.refresh(new_combo)
    return new_combo

def build_outfit_recommendation_dict(
    combo: OutfitCombo,
    weather_desc: Optional[str] = None,
    weather_adjusted: bool = True
) -> Dict[str, Any]:
    """Đóng gói thông tin bộ đồ thành dict phù hợp với OutfitRecommendation schema"""
    items_list = [
        {
            "id": cast(int, item.id),
            "name": f"{item.color_name or get_color_name_from_hex(str(item.color_code))} {item.category}",
            "category": item.category,
            "color_name": item.color_name or get_color_name_from_hex(str(item.color_code)),
            "color_code": item.color_code,
            "style": item.style_tag,
            "style_tag": item.style_tag,
            "image_url": item.image_url,
            "is_ai_fixed": getattr(item, "is_ai_fixed", True)
        } for item in combo.items
    ]

    first_image = items_list[0]["image_url"] if items_list else None
    title = combo.style_type or "Curated Outfit Set"

    tags_list: List[str] = []
    for item in items_list:
        st = item.get("style_tag")
        if st and st not in tags_list:
            tags_list.append(st)
        cat = item.get("category")
        if cat and cat not in tags_list:
            tags_list.append(cat)

    if weather_desc:
        description = f"Tối ưu cho thời tiết {weather_desc}."
    else:
        description = f"Set đồ '{title}' phối hợp {len(items_list)} món trang phục chỉn chu cho ngày của bạn."

    return {
        "outfit_id": combo.id,
        "style_type": combo.style_type or "Daily Set",
        "title": title,
        "description": description,
        "image_url": first_image,
        "tags": tags_list,
        "weather_adjusted": weather_adjusted,
        "items": items_list
    }
