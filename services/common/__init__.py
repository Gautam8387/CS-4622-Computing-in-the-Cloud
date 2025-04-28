# ./services/common/__init__.py
from .logger import setup_logger
from .queue import add_transcoding_job, celery_app, redis_client, send_notification_job

# Import objects/functions needed by services
from .storage import download_from_s3, get_s3_presigned_url, upload_to_s3

# Define what gets imported when 'from common import *' is used (though explicit imports are better)
__all__ = [
    "setup_logger",
    "upload_to_s3",
    "download_from_s3",
    "get_s3_presigned_url",
    "celery_app",  # Shared Celery app instance
    "redis_client",  # Shared Redis client instance (use with caution regarding blocking ops)
    "add_transcoding_job",  # Function to send transcoding task
    "send_notification_job",  # Function to send notification task
]
