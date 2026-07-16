# app/services/storage.py
import boto3
import os
from botocore.exceptions import NoCredentialsError

def upload_image_to_s3(file_bytes, object_name):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
    
    try:
        # Upload file dạng bytes trực tiếp lên S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_name,
            Body=file_bytes,
            ContentType='image/png',
            ACL='public-read' # Để mobile có thể truy cập link trực tiếp
        )
        return f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
    except NoCredentialsError:
        return None