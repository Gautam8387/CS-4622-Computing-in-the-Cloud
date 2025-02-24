# ./services/transcoding-service/config.py
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
S3_BUCKET = os.getenv("S3_BUCKET", "fallback-bucket")  # Add S3 bucket name for fallback
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
