# app/services/color_extractor.py
import io
import numpy as np
from PIL import Image
from sklearn.cluster import MiniBatchKMeans
from typing import List, Dict, Any, Union

from app.services.color_math import rgb_to_hex, get_color_name_from_hex, get_color_group_from_hex
from app.core.logger import logger

def extract_dominant_colors(
    image_input: Union[bytes, str, Image.Image],
    n_colors: int = 3,
    max_dimension: int = 200
) -> List[Dict[str, Any]]:
    """
    Trích xuất bảng màu chủ đạo (Color Palette) từ ảnh trang phục sử dụng K-Means Clustering.
    
    Thuật toán:
    1. Đọc và resize ảnh để giảm số lượng pixel tính toán (tăng tốc độ xử lý xuống dưới 20ms).
    2. Bỏ các pixel trong suốt (Alpha < 50) để chỉ tập trung vào quần áo.
    3. Chạy MiniBatchKMeans để tìm n_colors cụm màu.
    4. Tính tỷ lệ % xuất hiện của từng màu và sắp xếp theo thứ tự giảm dần.
    """
    try:
        # 1. Đọc ảnh vào PIL Image
        if isinstance(image_input, bytes):
            image = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, str):
            image = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            image = image_input
        else:
            raise ValueError("Định dạng ảnh đầu vào không hợp lệ")

        # 2. Chuyển sang định dạng RGBA
        image = image.convert("RGBA")
        
        # Resize giữ nguyên tỷ lệ để tăng tốc độ tính toán (Thumbnail)
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.NEAREST)
        
        # 3. Chuyển đổi sang NumPy Array (H, W, 4)
        np_image = np.array(image)
        
        # Tách kênh RGB và kênh Alpha
        rgb_pixels = np_image[:, :, :3]
        alpha_channel = np_image[:, :, 3]
        
        # 4. Lọc mask: Chỉ lấy các pixel có alpha > 50 (bỏ nền trong suốt)
        mask = alpha_channel > 50
        valid_pixels = rgb_pixels[mask] # Shape: (N, 3)
        
        # Trường hợp ảnh rỗng hoặc toàn bộ là trong suốt
        if len(valid_pixels) == 0:
            return [{
                "hex_code": "#000000",
                "color_name": "Black",
                "percentage": 100.0
            }]
            
        # Nếu số pixel còn lại ít hơn số cụm k
        actual_k = min(n_colors, len(valid_pixels))
        
        # 5. Chạy MiniBatchKMeans (nhanh hơn Standard KMeans 5-10 lần, kết quả tương đương)
        kmeans = MiniBatchKMeans(
            n_clusters=actual_k,
            random_state=42,
            batch_size=1024,
            n_init=3
        )
        kmeans.fit(valid_pixels)
        
        # 6. Thống kê số lượng pixel thuộc từng cụm để tính tỷ lệ %
        labels = kmeans.labels_
        cluster_centers = kmeans.cluster_centers_ # Shape: (k, 3)
        
        counts = np.bincount(labels, minlength=actual_k)
        total_valid_pixels = len(valid_pixels)
        
        results = []
        for i in range(actual_k):
            r, g, b = cluster_centers[i]
            hex_code = rgb_to_hex(r, g, b)
            color_name = get_color_name_from_hex(hex_code)
            color_group = get_color_group_from_hex(hex_code)
            percentage = round((float(counts[i]) / float(total_valid_pixels)) * 100.0, 1)
            
            results.append({
                "hex_code": hex_code,
                "color_name": color_name,
                "color_group": color_group,
                "percentage": percentage
            })
            
        # Sắp xếp màu có tỷ lệ % xuất hiện nhiều nhất lên đầu
        results.sort(key=lambda x: x["percentage"], reverse=True)
        return results

    except Exception as e:
        logger.error(f"[Color Extractor Error] Lỗi khi trích xuất màu K-Means: {e}")
        return [{
            "hex_code": "#1E293B",
            "color_name": "Slate Gray",
            "percentage": 100.0
        }]
