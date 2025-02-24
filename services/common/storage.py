import os
import boto3
from services.api_gateway.config import S3_BUCKET, S3_ENDPOINT_URL

s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY')
)

def upload_to_s3(file, s3_key):
    s3_client.upload_fileobj(file, S3_BUCKET, s3_key)

def get_s3_url(s3_key):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': S3_BUCKET, 'Key': s3_key},
        ExpiresIn=3600  # 1 hour
    )