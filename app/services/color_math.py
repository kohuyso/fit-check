# app/services/color_math.py
import math

COLOR_DICTIONARY = {
    "#FFFFFF": "White",
    "#000000": "Black",
    "#0A192F": "Navy Blue",
    "#1E293B": "Slate Gray",
    "#2563EB": "Royal Blue",
    "#10B981": "Emerald Green",
    "#F59E0B": "Amber Gold",
    "#EF4444": "Crimson Red",
    "#8B5CF6": "Purple",
    "#D97706": "Camel",
    "#6B7280": "Charcoal",
    "#F3F4F6": "Off-White",
    "#9CA3AF": "Light Gray",
    "#1F2937": "Dark Charcoal",
    "#4B5563": "Cool Gray"
}

def hex_to_rgb(hex_str: str):
    hex_str = str(hex_str).lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    elif len(hex_str) != 6:
        return (128, 128, 128)
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return (128, 128, 128)

def get_color_name_from_hex(hex_str: str) -> str:
    """Tự động tính toán tên màu hiển thị gần nhất dựa trên mã HEX"""
    if not hex_str:
        return "Classic"
    hex_clean = str(hex_str).upper()
    if hex_clean in COLOR_DICTIONARY:
        return COLOR_DICTIONARY[hex_clean]
    
    target_rgb = hex_to_rgb(hex_str)
    best_name = "Classic"
    min_dist = float('inf')
    
    for known_hex, name in COLOR_DICTIONARY.items():
        known_rgb = hex_to_rgb(known_hex)
        dist = math.sqrt(sum((t - k) ** 2 for t, k in zip(target_rgb, known_rgb)))
        if dist < min_dist:
            min_dist = dist
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
    def luminance(r, g, b):
        a = [v / 255.0 for v in (r, g, b)]
        a = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in a]
        return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722

    l1 = luminance(*rgb1)
    l2 = luminance(*rgb2)
    
    brightest = max(l1, l2)
    darkest = min(l1, l2)
    return (brightest + 0.05) / (darkest + 0.05)
