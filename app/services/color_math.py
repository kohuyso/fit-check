# app/services/color_math.py
import math
from typing import Tuple, Dict, Any, List, Optional

COLOR_DICTIONARY: Dict[str, str] = {
    # Whites & Creams
    "#FFFFFF": "Pure White",
    "#F8FAFC": "Off-White",
    "#FDFBF7": "Ivory",
    "#FFFDD0": "Cream",
    "#F5F5DC": "Beige",
    "#F5F5F0": "Eggshell",
    "#E2E8F0": "Light Gray / Off-White",

    # Blacks & Grays
    "#000000": "Jet Black",
    "#09090B": "True Black",
    "#18181B": "Black Charcoal",
    "#27272A": "Charcoal Gray",
    "#3F3F46": "Dark Slate Gray",
    "#1E293B": "Slate Gray",
    "#334155": "Dark Charcoal",
    "#475569": "Slate",
    "#64748B": "Cool Gray",
    "#71717A": "Neutral Gray",
    "#94A3B8": "Steel Gray",
    "#A1A1AA": "Medium Gray",
    "#CBD5E1": "Light Slate",
    "#D4D4D8": "Silver Gray",
    "#E4E4E7": "Platinum Gray",

    # Reds, Maroons & Wines
    "#381517": "Deep Maroon / Wine Red",
    "#4A0E17": "Dark Maroon",
    "#2A080C": "Dark Cherry",
    "#4C0519": "Black Cherry / Berry",
    "#722F37": "Wine Red",
    "#800020": "Burgundy",
    "#881337": "Deep Burgundy",
    "#991B1B": "Crimson Red",
    "#B91C1C": "Ruby Red",
    "#DC2626": "Bright Red",
    "#EF4444": "Scarlet Red",
    "#F87171": "Coral Red",
    "#E11D48": "Rose Red",
    "#BE123C": "Carmine Red",

    # Pinks & Corals
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

    # Purples, Violets & Plums
    "#3B0764": "Dark Violet",
    "#581C87": "Deep Purple",
    "#6B21A8": "Royal Purple",
    "#7E22CE": "Purple",
    "#8B5CF6": "Lavender Violet",
    "#A855F7": "Bright Purple",
    "#C084FC": "Pastel Purple / Lilac",
    "#DDD6FE": "Soft Lavender",
    "#701A75": "Plum",
    "#86198F": "Dark Fuchsia",
    "#E879F9": "Fuchsia",

    # Blues & Navies
    "#020617": "Blackened Navy",
    "#0A192F": "Midnight Navy",
    "#0F172A": "Dark Navy Blue",
    "#172554": "Deep Navy Blue",
    "#1E3A8A": "Navy Blue",
    "#1E40AF": "Dark Royal Blue",
    "#1D4ED8": "Cobalt Blue",
    "#2563EB": "Royal Blue",
    "#3B82F6": "Classic Blue",
    "#60A5FA": "Cornflower Blue",
    "#93C5FD": "Light Sky Blue",
    "#BFDBFE": "Baby Blue",
    "#0284C7": "Ocean Blue",
    "#0369A1": "Deep Sky Blue",
    "#38BDF8": "Sky Blue",
    "#7DD3FC": "Pastel Blue",
    "#0891B2": "Cerulean Blue",
    "#06B6D4": "Cyan / Aqua",
    "#0E7490": "Teal Blue",
    "#155E75": "Deep Teal",
    "#164E63": "Dark Petrol Blue",

    # Greens & Olives
    "#022C22": "Dark Pine Green",
    "#064E3B": "Deep Forest Green",
    "#065F46": "Forest Green",
    "#047857": "Pine Green",
    "#059669": "Emerald Green",
    "#10B981": "Jade Green",
    "#34D399": "Mint Green",
    "#6EE7B7": "Pastel Green",
    "#A7F3D0": "Soft Mint",
    "#14532D": "Hunter Green",
    "#166534": "Dark Green",
    "#15803D": "Classic Green",
    "#14532D": "Army Green",
    "#3F6212": "Dark Olive",
    "#4D7C0F": "Moss Green",
    "#65A30D": "Olive Green",
    "#84CC16": "Lime / Olive",
    "#A3E635": "Chartreuse",
    "#0F766E": "Teal Green",
    "#115E59": "Peacock Green",
    "#134E4A": "Dark Teal",
    "#2DD4BF": "Turquoise",

    # Yellows, Oranges & Golds
    "#FEF08A": "Pastel Yellow",
    "#FDE047": "Butter Yellow",
    "#FACC15": "Lemon Yellow",
    "#EAB308": "Mustard Yellow",
    "#CA8A04": "Ochre / Gold",
    "#A16207": "Deep Gold / Mustard",
    "#F59E0B": "Amber Gold",
    "#F97316": "Bright Orange",
    "#EA580C": "Orange",
    "#C2410C": "Rust / Terracotta",
    "#9A3412": "Burnt Orange / Brick",

    # Browns, Tans & Earth Tones
    "#271406": "Dark Coffee",
    "#3E2723": "Espresso Brown",
    "#451A03": "Deep Dark Brown",
    "#78350F": "Dark Chocolate Brown",
    "#7C2D12": "Mahogany Brown",
    "#92400E": "Mocha Brown",
    "#B45309": "Chestnut Brown",
    "#D97706": "Camel / Cognac",
    "#B8860B": "Dark Goldenrod",
    "#CD7F32": "Bronze",
    "#D2B48C": "Tan",
    "#C4A484": "Khaki",
    "#EEDC82": "Flax / Sand",
    "#D7C4B7": "Warm Taupe",
    "#8D6E63": "Taupe Brown"
}

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

def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Chuyển đổi RGB sang mã HEX chuẩn hoa #RRGGBB"""
    r_val = max(0, min(255, int(round(r))))
    g_val = max(0, min(255, int(round(g))))
    b_val = max(0, min(255, int(round(b))))
    return f"#{r_val:02X}{g_val:02X}{b_val:02X}"

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
    
    for known_hex, name in COLOR_DICTIONARY.items():
        known_rgb = hex_to_rgb(known_hex)
        known_lab = rgb_to_cielab(*known_rgb)
        
        delta_e = calculate_delta_e_cie76(target_lab, known_lab)
        if delta_e < min_delta_e:
            min_delta_e = delta_e
            best_name = name
            
    return best_name

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

