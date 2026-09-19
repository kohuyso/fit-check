# app/services/color_math.py
import math
import functools
from typing import Tuple, Dict, Any, List, Optional

COLOR_GROUPS: Dict[str, Dict[str, str]] = {
    "Whites & Creams": {
        "#FFFFFF": "Pure White",
        "#FAFAFA": "Snow White",
        "#F8FAFC": "Off-White",
        "#FDFBF7": "Ivory",
        "#FFFDD0": "Cream",
        "#F5F5DC": "Beige",
        "#F5F5F0": "Eggshell",
        "#E2E8F0": "Light Gray / Off-White",
        "#FAF0E6": "Linen",
        "#FDF5E6": "Old Lace",
        "#F0EAE1": "Alabaster",
        "#EFEBD9": "Ecru / Bone",
    },
    "Blacks & Charcoals": {
        "#000000": "Jet Black",
        "#09090B": "True Black",
        "#121212": "Midnight Black",
        "#18181B": "Black Charcoal",
        "#1C1917": "Obsidian Black",
        "#242424": "Onyx Black",
        "#2D2D2D": "Ebony",
        "#333333": "Pitch Black",
    },
    "Grays & Silvers": {
        "#27272A": "Charcoal Gray",
        "#3F3F46": "Dark Slate Gray",
        "#1E293B": "Slate Gray",
        "#334155": "Dark Charcoal",
        "#475569": "Slate",
        "#52525B": "Graphite Gray",
        "#64748B": "Cool Gray",
        "#71717A": "Neutral Gray",
        "#78716C": "Warm Gray",
        "#94A3B8": "Steel Gray",
        "#A1A1AA": "Medium Gray",
        "#B0BEC5": "Ash Gray",
        "#CBD5E1": "Light Slate",
        "#D4D4D8": "Silver Gray",
        "#E4E4E7": "Platinum Gray",
        "#ECEFF1": "Fog Gray",
        "#9E9E9E": "Pewter Gray",
    },
    "Beiges, Sands & Tans": {
        "#EDE6D6": "Oat Beige",
        "#F5F5DC": "Classic Beige",
        "#EEDC82": "Flax / Sand",
        "#ECD9BA": "Desert Sand",
        "#E4D5B7": "Sandstone",
        "#D2B48C": "Tan",
        "#C4A484": "Khaki",
        "#BDB76B": "Dark Khaki",
        "#E6D7C3": "Almond Beige",
        "#D7C4B7": "Warm Taupe",
        "#C2B280": "Chino Tan",
        "#E3DAC9": "Bone Beige",
    },
    "Browns, Mochas & Chocolates": {
        "#271406": "Dark Coffee",
        "#3E2723": "Espresso Brown",
        "#451A03": "Deep Dark Brown",
        "#4A2E18": "Dark Walnut",
        "#5C4033": "Dark Brown",
        "#78350F": "Dark Chocolate Brown",
        "#7C2D12": "Mahogany Brown",
        "#8B4513": "Saddle Brown",
        "#8D6E63": "Taupe Brown",
        "#92400E": "Mocha Brown",
        "#A0522D": "Sienna Brown",
        "#B45309": "Chestnut Brown",
        "#6F4E37": "Coffee Brown",
        "#855E42": "Cocoa Brown",
        "#967117": "Sand Dune Brown",
    },
    "Earth Tones, Terracottas & Rusts": {
        "#C2410C": "Rust / Terracotta",
        "#9A3412": "Burnt Orange / Brick",
        "#B94700": "Burnt Sienna",
        "#CC4E2A": "Terracotta Red",
        "#D97706": "Camel / Cognac",
        "#B8860B": "Dark Goldenrod",
        "#CD7F32": "Bronze",
        "#A0522D": "Clay Brown",
        "#8C3617": "Adobe Clay",
        "#793822": "Sepia Rust",
        "#6A381F": "Raw Umber",
    },
    "Reds, Maroons & Burgundies": {
        "#381517": "Deep Maroon / Wine Red",
        "#4A0E17": "Dark Maroon",
        "#2A080C": "Dark Cherry",
        "#4C0519": "Black Cherry / Berry",
        "#58111A": "Oxblood",
        "#722F37": "Wine Red",
        "#800020": "Burgundy",
        "#881337": "Deep Burgundy",
        "#6B1020": "Bordeaux Wine",
        "#991B1B": "Crimson Red",
        "#B91C1C": "Ruby Red",
        "#C00000": "Classic Red",
        "#DC2626": "Bright Red",
        "#EF4444": "Scarlet Red",
        "#E11D48": "Rose Red",
        "#BE123C": "Carmine Red",
        "#730F1E": "Garnet Red",
    },
    "Pinks, Peaches & Corals": {
        "#FB7185": "Rose Pink",
        "#FDA4AF": "Blush Pink",
        "#FECDD3": "Baby Pink",
        "#FBCFE8": "Pastel Pink",
        "#F472B6": "Pink",
        "#EC4899": "Hot Pink / Magenta",
        "#DB2777": "Deep Pink",
        "#BE185D": "Dark Magenta",
        "#FF7F50": "Coral",
        "#FB923C": "Peach Coral",
        "#FED7AA": "Light Peach",
        "#F87171": "Coral Red",
        "#D88373": "Dusty Rose",
        "#E8A598": "Ballet Pink",
        "#FA8072": "Salmon Pink",
        "#F4A460": "Sandy Peach",
    },
    "Oranges, Ambers & Spices": {
        "#F59E0B": "Amber Gold",
        "#F97316": "Bright Orange",
        "#EA580C": "Orange",
        "#FB8C00": "Tangerine",
        "#FF9800": "Mandarin Orange",
        "#FF6F00": "Marigold",
        "#D84315": "Paprika Orange",
        "#E65100": "Tiger Lily Orange",
        "#F39C12": "Saffron Orange",
    },
    "Yellows, Golds & Mustards": {
        "#FEF08A": "Pastel Yellow",
        "#FDE047": "Butter Yellow",
        "#FACC15": "Lemon Yellow",
        "#EAB308": "Mustard Yellow",
        "#CA8A04": "Ochre / Gold",
        "#A16207": "Deep Gold / Mustard",
        "#FFD700": "Golden Yellow",
        "#D4AF37": "Metallic Gold",
        "#DAA520": "Goldenrod",
        "#C5A059": "Antique Gold",
        "#E4D00A": "Citrine Yellow",
    },
    "Greens, Olives & Armies": {
        "#022C22": "Dark Pine Green",
        "#064E3B": "Deep Forest Green",
        "#065F46": "Forest Green",
        "#047857": "Pine Green",
        "#059669": "Emerald Green",
        "#10B981": "Jade Green",
        "#14532D": "Hunter Green",
        "#166534": "Dark Green",
        "#15803D": "Classic Green",
        "#1B4D3E": "Brunswick Green",
        "#2E7D32": "Grass Green",
        "#3F6212": "Dark Olive",
        "#4D7C0F": "Moss Green",
        "#65A30D": "Olive Green",
        "#556B2F": "Military Olive",
        "#4B5320": "Army Green",
        "#84CC16": "Lime / Olive",
        "#A3E635": "Chartreuse",
        "#2F4F4F": "Dark Slate Cypress",
    },
    "Sages, Mints & Eucalyptus": {
        "#9CAF88": "Sage Green",
        "#879B7F": "Muted Sage",
        "#7A8B7B": "Dusty Sage",
        "#5F7565": "Eucalyptus Green",
        "#A3B18A": "Celadon Sage",
        "#34D399": "Mint Green",
        "#6EE7B7": "Pastel Green",
        "#A7F3D0": "Soft Mint",
        "#99F6E4": "Pale Aqua Mint",
        "#8FBC8F": "Dark Sea Green",
        "#D8E2DC": "Pistachio Mist",
        "#C8D6AF": "Laurel Green",
    },
    "Teals, Turquoises & Aquas": {
        "#0F766E": "Teal Green",
        "#115E59": "Peacock Green",
        "#134E4A": "Dark Teal",
        "#0E7490": "Teal Blue",
        "#155E75": "Deep Teal",
        "#164E63": "Dark Petrol Blue",
        "#0891B2": "Cerulean Blue",
        "#06B6D4": "Cyan / Aqua",
        "#2DD4BF": "Turquoise",
        "#20B2AA": "Light Sea Green",
        "#008080": "Classic Teal",
        "#40E0D0": "Bright Turquoise",
        "#48D1CC": "Medium Turquoise",
        "#7FFFD4": "Aquamarine",
    },
    "Blues & Navies": {
        "#020617": "Blackened Navy",
        "#0A192F": "Midnight Navy",
        "#0F172A": "Dark Navy Blue",
        "#172554": "Deep Navy Blue",
        "#1E3A8A": "Navy Blue",
        "#1E40AF": "Dark Royal Blue",
        "#1D4ED8": "Cobalt Blue",
        "#2563EB": "Royal Blue",
        "#3B82F6": "Classic Blue",
        "#4169E1": "Royal Oxford Blue",
        "#0047AB": "Cobalt",
        "#0F52BA": "Sapphire Blue",
        "#60A5FA": "Cornflower Blue",
        "#0284C7": "Ocean Blue",
        "#0369A1": "Deep Sky Blue",
    },
    "Denim, Indigos & Sky Blues": {
        "#1C3144": "Raw Denim Blue",
        "#2B4C6F": "Dark Indigo Denim",
        "#3E6B89": "Washed Denim",
        "#5D8AA8": "Steel Denim",
        "#7393B3": "Chambray Blue",
        "#38BDF8": "Sky Blue",
        "#7DD3FC": "Pastel Sky Blue",
        "#93C5FD": "Light Sky Blue",
        "#BFDBFE": "Baby Blue",
        "#BAE6FD": "Ice Blue",
        "#B0C4DE": "Light Steel Blue",
        "#C6D8D3": "Powder Blue",
        "#CCCCFF": "Periwinkle Blue",
    },
    "Purples, Lavenders & Lilacs": {
        "#3B0764": "Dark Violet",
        "#4A0E4E": "Imperial Purple",
        "#581C87": "Deep Purple",
        "#6B21A8": "Royal Purple",
        "#7E22CE": "Purple",
        "#8B5CF6": "Lavender Violet",
        "#A855F7": "Bright Purple",
        "#C084FC": "Pastel Purple / Lilac",
        "#D8B4FE": "Lilac Haze",
        "#DDD6FE": "Soft Lavender",
        "#E9D5FF": "Pale Lavender",
        "#B39DDB": "Wisteria Purple",
        "#8E24AA": "Deep Orchid",
        "#AB47BC": "Orchid",
    },
    "Plums, Berries & Mauves": {
        "#701A75": "Plum",
        "#4A154B": "Deep Plum",
        "#86198F": "Dark Fuchsia",
        "#E879F9": "Fuchsia",
        "#592A45": "Mulberry",
        "#481D24": "Blackberry",
        "#9C51B6": "Boysenberry",
        "#915C83": "Dusty Mauve",
        "#B784A7": "Light Mauve",
        "#673147": "Rose Wine",
    },
    "Pastels & Soft Shades": {
        "#FCE7F3": "Pastel Blossom Pink",
        "#EDE9FE": "Pastel Lavender Mist",
        "#E0F2FE": "Pastel Sky Ice",
        "#DCFCE7": "Pastel Fresh Mint",
        "#FEF9C3": "Pastel Butter Cream",
        "#FFEDD5": "Pastel Peach Cream",
        "#F3E8FF": "Pastel Soft Lilac",
        "#E0F7FA": "Pastel Frost Aqua",
        "#F1F5F9": "Pastel Slate Mist",
    },
    "Neons & Cyberpunk": {
        "#39FF14": "Electric Neon Lime",
        "#CCFF00": "Cyber Neon Yellow",
        "#00FF66": "Acid Neon Green",
        "#FF007F": "Neon Cyber Pink",
        "#FF1493": "Deep Neon Pink",
        "#00F0FF": "Cyber Cyan / Neon Blue",
        "#FF5F00": "Laser Neon Orange",
        "#FF0033": "High-Voltage Red",
        "#E000FF": "Neon Violet",
    },
    "Metallics & Shimmers": {
        "#D4AF37": "Champagne Metallic Gold",
        "#CFB53B": "Old Gold Shimmer",
        "#B76E79": "Rose Gold Metallic",
        "#C0C0C0": "Pure Silver Metallic",
        "#E5E4E2": "Platinum Shimmer",
        "#727472": "Gunmetal Metallic",
        "#8A9A5B": "Antique Bronze Shimmer",
        "#B87333": "Copper Metallic",
        "#6E7F80": "Pewter Metallic",
    },
}

# Tự động gộp toàn bộ vào COLOR_DICTIONARY để tương thích 100% với mã nguồn hiện tại
COLOR_DICTIONARY: Dict[str, str] = {}
HEX_TO_COLOR_GROUP: Dict[str, str] = {}

for _group_name, _colors in COLOR_GROUPS.items():
    for _hex_code, _name in _colors.items():
        COLOR_DICTIONARY[_hex_code] = _name
        HEX_TO_COLOR_GROUP[_hex_code] = _group_name

# Phân loại họ màu chính (Color Family) rút gọn cho Mobile Filter
COLOR_GROUP_TO_FAMILY: Dict[str, str] = {
    "Whites & Creams": "White",
    "Blacks & Charcoals": "Black",
    "Grays & Silvers": "Gray",
    "Beiges, Sands & Tans": "Beige",
    "Browns, Mochas & Chocolates": "Brown",
    "Earth Tones, Terracottas & Rusts": "Brown",
    "Reds, Maroons & Burgundies": "Red",
    "Pinks, Peaches & Corals": "Pink",
    "Oranges, Ambers & Spices": "Orange",
    "Yellows, Golds & Mustards": "Yellow",
    "Greens, Olives & Armies": "Green",
    "Sages, Mints & Eucalyptus": "Green",
    "Teals, Turquoises & Aquas": "Teal",
    "Blues & Navies": "Blue",
    "Denim, Indigos & Sky Blues": "Blue",
    "Purples, Lavenders & Lilacs": "Purple",
    "Plums, Berries & Mauves": "Purple",
    "Pastels & Soft Shades": "Pastel",
    "Neons & Cyberpunk": "Neon",
    "Metallics & Shimmers": "Metallic",
}

@functools.lru_cache(maxsize=2048)
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Chuyển đổi chuỗi HEX sang tuple (R, G, B) [0..255]"""
    hex_clean = str(hex_str).lstrip('#').strip()
    if len(hex_clean) == 3:
        hex_clean = ''.join([c * 2 for c in hex_clean])
    elif len(hex_clean) != 6:
        return (128, 128, 128)
    try:
        return (int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16))
    except ValueError:
        return (128, 128, 128)

@functools.lru_cache(maxsize=2048)
def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Chuyển đổi RGB sang mã HEX chuẩn hoa #RRGGBB"""
    r_val = max(0, min(255, int(round(r))))
    g_val = max(0, min(255, int(round(g))))
    b_val = max(0, min(255, int(round(b))))
    return f"#{r_val:02X}{g_val:02X}{b_val:02X}"

@functools.lru_cache(maxsize=2048)
def rgb_to_cielab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """
    Chuyển đổi không gian màu: sRGB -> CIE XYZ -> CIELAB (D65 Standard Illuminant)
    Đại số tuyến tính & chuẩn hóa phi tuyến tính Gamma.
    """
    # 1. Chuẩn hóa sRGB về [0, 1] và khử Gamma (Linearization)
    rgb = [v / 255.0 for v in (r, g, b)]
    linear_rgb = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 
        for v in rgb
    ]
    
    # 2. Nhân ma trận chuyển đổi từ sRGB sang không gian XYZ (Ma trận D65)
    X = linear_rgb[0] * 0.4124564 + linear_rgb[1] * 0.3575761 + linear_rgb[2] * 0.1804375
    Y = linear_rgb[0] * 0.2126729 + linear_rgb[1] * 0.7151522 + linear_rgb[2] * 0.0721750
    Z = linear_rgb[0] * 0.0193339 + linear_rgb[1] * 0.1191920 + linear_rgb[2] * 0.9503041

    # 3. Chuẩn hóa theo điểm trắng chuẩn D65 (Xn, Yn, Zn)
    Xn, Yn, Zn = 0.95047, 1.00000, 1.08883
    xr, yr, zr = X / Xn, Y / Yn, Z / Zn

    # 4. Hàm chuyển đổi phi tuyến tính f(t)
    def f(t: float) -> float:
        delta = 6.0 / 29.0
        return t ** (1.0 / 3.0) if t > delta ** 3 else (t / (3.0 * delta ** 2)) + (4.0 / 29.0)

    # 5. Tính tọa độ L*, a*, b*
    lab_l = 116.0 * f(yr) - 16.0
    lab_a = 500.0 * (f(xr) - f(yr))
    lab_b = 200.0 * (f(yr) - f(zr))

    return (lab_l, lab_a, lab_b)

@functools.lru_cache(maxsize=4096)
def calculate_delta_e_cie76(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """
    Tính khoảng cách cảm nhận màu sắc Delta-E (CIE 1976):
    ΔE = sqrt((L1 - L2)^2 + (a1 - a2)^2 + (b1 - b2)^2)
    """
    return math.sqrt(
        (lab1[0] - lab2[0]) ** 2 +
        (lab1[1] - lab2[1]) ** 2 +
        (lab1[2] - lab2[2]) ** 2
    )

# Bộ nhớ đệm CIELAB tính trước để tăng tốc độ Delta-E tìm kiếm lên gấp 10 lần
_COLOR_LAB_CACHE: List[Tuple[str, str, str, Tuple[float, float, float]]] = [
    (hex_code, name, HEX_TO_COLOR_GROUP[hex_code], rgb_to_cielab(*hex_to_rgb(hex_code)))
    for hex_code, name in COLOR_DICTIONARY.items()
]

@functools.lru_cache(maxsize=2048)
def get_color_name_from_hex(hex_str: str) -> str:
    """
    Tìm tên màu gần nhất trong từ điển bằng cách tìm min Delta-E (CIELAB)
    thay vì khoảng cách RGB hình học thông thường.
    """
    if not hex_str:
        return "Classic"
        
    target_rgb = hex_to_rgb(hex_str)
    target_lab = rgb_to_cielab(*target_rgb)
    
    best_name = "Classic"
    min_delta_e = float('inf')
    
    for _, name, _, known_lab in _COLOR_LAB_CACHE:
        delta_e = calculate_delta_e_cie76(target_lab, known_lab)
        if delta_e < min_delta_e:
            min_delta_e = delta_e
            best_name = name
            
    return best_name

@functools.lru_cache(maxsize=2048)
def get_color_group_from_hex(hex_str: str) -> str:
    """
    Tìm nhóm màu thời trang chi tiết (ví dụ: 'Denim, Indigos & Sky Blues', 'Sages, Mints & Eucalyptus')
    gần nhất với mã HEX sử dụng không gian màu CIELAB và Delta-E 76.
    """
    if not hex_str:
        return "Grays & Silvers"
        
    target_rgb = hex_to_rgb(hex_str)
    target_lab = rgb_to_cielab(*target_rgb)
    
    best_group = "Grays & Silvers"
    min_delta_e = float('inf')
    
    for _, _, group_name, known_lab in _COLOR_LAB_CACHE:
        delta_e = calculate_delta_e_cie76(target_lab, known_lab)
        if delta_e < min_delta_e:
            min_delta_e = delta_e
            best_group = group_name
            
    return best_group

@functools.lru_cache(maxsize=2048)
def get_color_family_from_hex(hex_str: str) -> str:
    """
    Trả về họ màu chính rút gọn (ví dụ: 'Blue', 'Green', 'Red', 'Black', 'White', 'Beige',...)
    phục vụ việc lọc (filter) trên Mobile app và Web frontend.
    """
    group = get_color_group_from_hex(hex_str)
    return COLOR_GROUP_TO_FAMILY.get(group, "Neutral")

@functools.lru_cache(maxsize=2048)
def get_color_tone_from_hex(hex_str: str) -> str:
    """
    Xác định sắc thái tông màu: 'Warm', 'Cool', hoặc 'Neutral'
    dựa trên tọa độ CIELAB (L*, a*, b*).
    - Neutral: bão hòa thấp (chroma < 14) hoặc L* rất sáng / tối
    - Warm: ngả đỏ, cam, vàng, nâu
    - Cool: ngả xanh lam, xanh lục đậm, tím lạnh
    """
    rgb = hex_to_rgb(hex_str)
    l_val, a_val, b_val = rgb_to_cielab(*rgb)
    chroma = math.sqrt(a_val ** 2 + b_val ** 2)
    
    if chroma < 14.0 or l_val >= 94.0 or l_val <= 12.0:
        return "Neutral"
    
    hue_angle = (math.degrees(math.atan2(b_val, a_val)) + 360) % 360
    
    if 20 <= hue_angle <= 120 or 340 <= hue_angle <= 360 or 0 <= hue_angle <= 20:
        return "Warm"
    else:
        return "Cool"

def list_all_color_groups() -> List[str]:
    """Trả về danh sách toàn bộ 20 nhóm màu thời trang có sẵn"""
    return list(COLOR_GROUPS.keys())

def get_color_details(hex_str: str) -> Dict[str, Any]:
    """
    Trả về thông tin phân tích toàn diện về màu sắc:
    Tên chuẩn thời trang, nhóm màu, họ màu, tông màu, mã RGB và tọa độ CIELAB.
    """
    cleaned_hex = hex_str.strip() if hex_str else "#000000"
    rgb = hex_to_rgb(cleaned_hex)
    lab = rgb_to_cielab(*rgb)
    
    name = get_color_name_from_hex(cleaned_hex)
    group = get_color_group_from_hex(cleaned_hex)
    family = COLOR_GROUP_TO_FAMILY.get(group, "Neutral")
    tone = get_color_tone_from_hex(cleaned_hex)
    
    return {
        "hex": rgb_to_hex(*rgb),
        "name": name,
        "color_group": group,
        "color_family": family,
        "tone": tone,
        "is_neutral": tone == "Neutral",
        "rgb": {
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2]
        },
        "cielab": {
            "l": round(lab[0], 2),
            "a": round(lab[1], 2),
            "b": round(lab[2], 2)
        }
    }

@functools.lru_cache(maxsize=2048)
def calculate_contrast_ratio(color1_hex: str, color2_hex: str) -> float:
    """
    Thuật toán kiểm tra độ tương phản giữa 2 món đồ (ví dụ: Áo và Blazer).
    Tránh việc AI gợi ý phối 2 món đồ có màu quá giống nhau nhưng lệch tông gây mất thẩm mỹ.
    """
    rgb1 = hex_to_rgb(color1_hex)
    rgb2 = hex_to_rgb(color2_hex)
    
    # Tính độ sáng tương đối (Relative Luminance) chuẩn WCAG
    def luminance(r: int, g: int, b: int) -> float:
        a = [v / 255.0 for v in (r, g, b)]
        a = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in a]
        return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722

    l1 = luminance(*rgb1)
    l2 = luminance(*rgb2)
    
    brightest = max(l1, l2)
    darkest = min(l1, l2)
    return (brightest + 0.05) / (darkest + 0.05)

@functools.lru_cache(maxsize=2048)
def evaluate_color_compatibility(color1_hex: str, color2_hex: str) -> Dict[str, Any]:
    """
    Đánh giá mức độ hài hòa giữa 2 màu trang phục dựa trên độ sáng L* và Delta-E.
    Tránh lỗi thời trang: Phối 2 màu quá gần nhau nhưng lệch sắc độ (Color Clash).
    """
    rgb1 = hex_to_rgb(color1_hex)
    rgb2 = hex_to_rgb(color2_hex)
    
    lab1 = rgb_to_cielab(*rgb1)
    lab2 = rgb_to_cielab(*rgb2)
    
    delta_e = calculate_delta_e_cie76(lab1, lab2)
    delta_lightness = abs(lab1[0] - lab2[0])
    
    is_clashing = False
    clash_reason = ""
    
    if 2.0 < delta_e < 12.0 and delta_lightness < 15.0:
        is_clashing = True
        clash_reason = "Hai màu quá gần nhau nhưng lệch sắc độ, dễ tạo cảm giác cũ hoặc phối lỗi."
        
    return {
        "delta_e": round(delta_e, 2),
        "lightness_difference": round(delta_lightness, 2),
        "is_clashing": is_clashing,
        "clash_reason": clash_reason
    }


def evaluate_outfit_palette_compatibility(hex_colors: List[str]) -> Dict[str, Any]:
    """
    Đánh giá mức độ hài hòa tổng thể của một bảng phối màu nhiều món đồ (3-5 items) trong Outfit.
    Sử dụng không gian màu CIELAB, Delta-E 76 và quy tắc phối màu quang học.
    """
    cleaned_hexes = [h.strip() for h in hex_colors if h and isinstance(h, str) and h.strip().startswith("#")]
    if not cleaned_hexes:
        return {
            "harmony_score": 80,
            "harmony_type": "Neutral Harmony",
            "is_harmonious": True,
            "clashes": [],
            "feedback": "Không có thông tin mã màu để phân tích."
        }

    if len(cleaned_hexes) == 1:
        color_name = get_color_name_from_hex(cleaned_hexes[0])
        return {
            "harmony_score": 95,
            "harmony_type": "Monochrome Tone",
            "is_harmonious": True,
            "clashes": [],
            "feedback": f"Trang phục đơn sắc tông {color_name} thanh lịch."
        }

    clashes: List[Dict[str, Any]] = []
    pairwise_delta_es: List[float] = []
    
    for i in range(len(cleaned_hexes)):
        for j in range(i + 1, len(cleaned_hexes)):
            c1, c2 = cleaned_hexes[i], cleaned_hexes[j]
            comp = evaluate_color_compatibility(c1, c2)
            pairwise_delta_es.append(comp["delta_e"])
            if comp["is_clashing"]:
                clashes.append({
                    "color_1": c1,
                    "color_1_name": get_color_name_from_hex(c1),
                    "color_2": c2,
                    "color_2_name": get_color_name_from_hex(c2),
                    "reason": comp["clash_reason"]
                })

    avg_delta_e = sum(pairwise_delta_es) / len(pairwise_delta_es) if pairwise_delta_es else 0.0

    # Phân loại phong cách phối màu
    if len(clashes) > 0:
        harmony_type = "Color Clash Detected"
        is_harmonious = False
        harmony_score = max(40, int(80 - (len(clashes) * 20)))
        feedback = f"Phát hiện {len(clashes)} cặp màu bị xung đột sắc độ nhẹ. Hãy cân nhắc đổi một trong hai món sang màu trung tính."
    elif avg_delta_e < 18.0:
        harmony_type = "Monochromatic / Ton-sur-Ton"
        is_harmonious = True
        harmony_score = 92
        feedback = "Phối màu Ton-sur-Ton (đồng điệu sắc thái) rất tinh tế và hiện đại."
    elif 18.0 <= avg_delta_e <= 45.0:
        harmony_type = "Harmonious & Balanced"
        is_harmonious = True
        harmony_score = 95
        feedback = "Độ tương phản vừa vặn, màu sắc bổ trợ hài hòa giữa các lớp trang phục."
    else:
        harmony_type = "High Contrast / Color Block"
        is_harmonious = True
        harmony_score = 88
        feedback = "Tương phản mạnh mẽ và cá tính (Color Blocking), tạo điểm nhấn thị giác nổi bật."

    return {
        "harmony_score": harmony_score,
        "harmony_type": harmony_type,
        "is_harmonious": is_harmonious,
        "clashes": clashes,
        "feedback": feedback
    }

