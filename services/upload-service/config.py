# ./services/upload-service/config.py
import os

from dotenv import load_dotenv

load_dotenv()

FLASK_ENV = os.getenv("FLASK_ENV", "production")
DEBUG = FLASK_ENV == "development"

# S3 Configuration (Essential for this service)
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # For MinIO/localstack
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")  # For MinIO/localstack
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")  # For MinIO/localstack

# Check essential S3 config
if not S3_BUCKET:
    print("Warning: Upload Service S3_BUCKET not configured.")
# Endpoint/Keys might be needed depending on environment (local vs AWS IAM role)
# if not S3_ENDPOINT_URL and not all([S3_ACCESS_KEY, S3_SECRET_KEY]):
#     print("Warning: Upload Service S3 endpoint or credentials may be needed.")

# Optional Redis URL if state is needed
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
