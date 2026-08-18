from typing import Optional
import boto3
from app.core.config import settings
from app.core.logger import logger

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