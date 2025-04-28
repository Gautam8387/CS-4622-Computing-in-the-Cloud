# ./services/api-gateway/config.py
import os

from dotenv import load_dotenv

load_dotenv()

FLASK_ENV = os.getenv("FLASK_ENV", "production")
DEBUG = FLASK_ENV == "development"

# CRITICAL: Use a strong, unique secret for JWT *validation*.
# This MUST match the secret used by the Auth Service for signing.
SECRET_KEY = os.getenv(
    "SECRET_KEY", "change-this-auth-service-secret-immediately"
)  # Should be same as Auth Service secret

# Service URLs
UPLOAD_SERVICE_URL = os.getenv("UPLOAD_SERVICE_URL", "http://localhost:5002")
AUTH_SERVICE_URL = os.getenv(
    "AUTH_SERVICE_URL", "http://localhost:5001"
)  # Optional: For token introspection

# Redis Config
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Celery Config (for task results)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Allowed upload formats (can be centralized)
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm", "wav", "mp3", "flac", "aac"}
