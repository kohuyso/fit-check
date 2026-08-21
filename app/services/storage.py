from typing import Optional
import boto3
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings
from app.core.logger import logger

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

def validate_and_get_image_extension(file: UploadFile) -> str:
    """
    Xác thực định dạng file ảnh từ Content-Type hoặc Extension của filename.
    Hỗ trợ chuẩn cho cả Web Browser và React Native Mobile (nơi Content-Type có thể là application/octet-stream).
    """
    filename = (file.filename or "").strip()
    filename_ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    content_type = (file.content_type or "").lower().strip()

    is_valid_mime = content_type in ALLOWED_IMAGE_MIME_TYPES
    is_valid_ext = filename_ext in ALLOWED_IMAGE_EXTENSIONS
    is_octet_stream = content_type in ("application/octet-stream", "binary/octet-stream", "")

    if not (is_valid_mime or is_valid_ext or (is_octet_stream and is_valid_ext)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận file ảnh định dạng PNG, JPG, JPEG hoặc WEBP."
        )

    if is_valid_ext:
        return filename_ext.lstrip(".")
    if is_valid_mime:
        mime_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
        }
        return mime_map.get(content_type, "jpg")
    return "jpg"

def upload_image_to_s3(file_bytes: bytes, object_name: str) -> Optional[str]:
    """Upload ảnh dưới dạng byte lên S3 và tạo Presigned URL có thời hạn 7 ngày"""
    access_key = settings.AWS_ACCESS_KEY_ID
    secret_key = settings.AWS_SECRET_ACCESS_KEY
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    if not (access_key and secret_key and bucket_name):
        logger.warning("AWS S3 parameters missing in environment settings.")
        return None
        
    if "your_" in access_key or "your_" in secret_key or "your_" in bucket_name:
        logger.warning("AWS S3 parameters contain placeholder values.")
        return None

    try:
        s3_kwargs = {
            'aws_access_key_id': access_key,
            'aws_secret_access_key': secret_key,
            'region_name': settings.AWS_REGION
        }
        if settings.AWS_ENDPOINT_URL:
            s3_kwargs['endpoint_url'] = settings.AWS_ENDPOINT_URL

        s3_client = boto3.client('s3', **s3_kwargs)
        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_name,
            Body=file_bytes,
            ContentType='image/png'
        )
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=604800  # 7 days
        )
        logger.info(f"AWS S3 Upload Success: {url}")
        return url
    except Exception as e:
        logger.exception(f"AWS S3 Upload Error for '{object_name}': {e}")
        return None