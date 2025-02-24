# ./services/upload-service/config.py
import os

S3_BUCKET = os.getenv("S3_BUCKET", "your-bucket-name")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
