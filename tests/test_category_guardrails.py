import pytest
from app.models.closet import ClothingItem
from app.services.outfit_service import (
    validate_outfit_category_composition,
    get_category_group
)

def create_mock_item(item_id: int, category: str, color_name: str = "Black", color_code: str = "#000000") -> ClothingItem:
    item = ClothingItem(
        id=item_id,
        user_id=1,
        image_url=f"https://example.com/item_{item_id}.png",
        category=category,
        color_name=color_name,
        color_code=color_code,
        style_tag="Casual"
    )
    return item

def test_category_group_resolver():
    assert get_category_group("Shirts") == "tops"
    assert get_category_group("t-shirt") == "tops"
    assert get_category_group("Áo sơ mi") == "tops"
    assert get_category_group("Jeans") == "bottoms"
    assert get_category_group("Quần tây") == "bottoms"
    assert get_category_group("Dresses") == "one_piece"
    assert get_category_group("Áo dài") == "one_piece"
    assert get_category_group("Jackets") == "outerwear"
    assert get_category_group("Sneakers") == "shoes"
    assert get_category_group("Bags") == "accessories"

def test_valid_basic_outfit():
    # 1 Áo + 1 Quần -> Hợp lệ
    item1 = create_mock_item(1, "Shirts")
    item2 = create_mock_item(2, "Pants")
    is_valid, err = validate_outfit_category_composition([item1, item2])
    assert is_valid is True
    assert err is None

def test_valid_dress_with_accessories():
    # 1 Đầm + 1 Giày + 1 Túi -> Hợp lệ
    dress = create_mock_item(1, "Dresses")
    shoes = create_mock_item(2, "Heels")
    bag = create_mock_item(3, "Bags")
    is_valid, err = validate_outfit_category_composition([dress, shoes, bag])
    assert is_valid is True
    assert err is None

def test_valid_vietnamese_categories():
    # Áo thun + Quần jean + Áo khoác -> Hợp lệ
    top = create_mock_item(1, "Áo thun")
    bot = create_mock_item(2, "Quần jean")
    coat = create_mock_item(3, "Áo khoác")
    is_valid, err = validate_outfit_category_composition([top, bot, coat])
    assert is_valid is True
    assert err is None

def test_conflict_multiple_bottoms():
    # 2 Quần (Jeans + Shorts) -> Bị từ chối
    item1 = create_mock_item(1, "Jeans")
    item2 = create_mock_item(2, "Shorts")
    item3 = create_mock_item(3, "Shirts")
    is_valid, err = validate_outfit_category_composition([item1, item2, item3])
    assert is_valid is False
    assert "Không thể chọn nhiều hơn 1 Quần" in err

def test_conflict_dress_with_pants():
    # Đầm + Quần dài -> Bị từ chối
    dress = create_mock_item(1, "Dresses")
    pants = create_mock_item(2, "Pants")
    is_valid, err = validate_outfit_category_composition([dress, pants])
    assert is_valid is False
    assert "Đã chọn Đầm liền" in err

def test_conflict_multiple_shoes():
    # 2 đôi giày trong cùng 1 set -> Bị từ chối
    item1 = create_mock_item(1, "Shirts")
    item2 = create_mock_item(2, "Pants")
    shoe1 = create_mock_item(3, "Sneakers")
    shoe2 = create_mock_item(4, "Boots")
    is_valid, err = validate_outfit_category_composition([item1, item2, shoe1, shoe2])
    assert is_valid is False
    assert "nhiều hơn 1 đôi Giày" in err

def test_incomplete_outfit_missing_bottom():
    # Chỉ có Áo + Áo khoác (thiếu Quần) -> Bị từ chối
    top = create_mock_item(1, "T-Shirts")
    jacket = create_mock_item(2, "Jackets")
    is_valid, err = validate_outfit_category_composition([top, jacket])
    assert is_valid is False
    assert "thiếu Quần" in err
