# app/services/color_math.py
def hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

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
    
    # Tính tỉ lệ tương phản
    brightest = max(l1, l2)
    darkest = min(l1, l2)
    return (brightest + 0.05) / (darkest + 0.05)