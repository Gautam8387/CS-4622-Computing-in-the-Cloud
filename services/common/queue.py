# ./services/common/queue.py
import os

import redis
from celery import Celery

from common import setup_logger  # Assuming logger is here

logger = setup_logger()

# --- Configuration ---
# Get Redis URL from environment, default for local dev
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Get Celery broker/backend URLs from environment
# Often the same as REDIS_URL, but allows flexibility
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# --- Redis Client (shared instance) ---
redis_client = None
try:
    # Use connection pooling for Redis client if used frequently outside Celery
    redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    redis_client = redis.Redis(connection_pool=redis_pool)
    redis_client.ping()  # Test connection
    logger.info("Common Redis client connected.")
except Exception as e:
    logger.error(f"Failed to connect common Redis client: {e}", exc_info=True)
    redis_client = None

# --- Celery App Initialization (shared instance) ---
# Define the Celery application instance once
# Services defining tasks will import *this* celery_app instance
# Services sending tasks will also import *this* instance
celery_app = Celery(
    "transcoding_tasks",  # Default name, can be overridden by worker
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[  # List modules containing tasks Celery should discover
        "services.transcoding_service.transcode",  # Path to transcoding tasks module
        "services.notification_service.notify",  # Path to notification tasks module
        # Add other task modules here if created
    ],
)

# Optional Celery configuration
celery_app.conf.update(
    task_serializer="json",  # Use json for task serialization
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",  # Use UTC timezone
    enable_utc=True,
    # Optional: configure task routing, rate limits, etc.
    # task_routes = {
    #     'services.notification_service.notify.*': {'queue': 'notifications'},
    # },
    broker_connection_retry_on_startup=True,  # Retry connection on startup
)

logger.info(
    f"Common Celery app initialized. Broker: {CELERY_BROKER_URL}, Backend: {CELERY_RESULT_BACKEND}"
)

# --- Task Sending Function ---


def add_transcoding_job(original_filename, s3_key, email, output_format):
    """
    Sends the main transcoding task to the Celery queue.

    Args:
        original_filename (str): The original name of the file.
        s3_key (str): The key of the uploaded file in the S3 raw prefix.
        email (str): User's email for notification.
        output_format (str): Desired output format.

    Returns:
        str: The Celery task ID.

    Raises:
        Exception: If sending the task fails.
    """
    try:
        # Ensure task name matches the @celery_app.task decorator in transcode.py
        # The name defaults to module_path.function_name if not specified in decorator
        # Using explicit name 'transcode_file' as defined in transcode.py's decorator
        task = celery_app.send_task(
            "transcode_file",  # Explicit task name matching decorator
            args=[original_filename, s3_key, email, output_format],
            # Optional: specify queue, priority, eta, etc.
            # queue='transcoding_queue'
        )
        logger.info(
            f"Sent task 'transcode_file' with ID: {task.id} for S3 key {s3_key}"
        )
        return task.id
    except Exception as e:
        logger.error(
            f"Failed to send transcoding task for {s3_key}: {e}", exc_info=True
        )
        # Re-raise or handle appropriately (e.g., mark job as failed immediately)
        raise


def send_notification_job(email, download_url, job_id):
    """Sends the notification task."""
    try:
        task = celery_app.send_task(
            "send_notification",  # Matches task name in notify.py
            args=[email, download_url, job_id],  # Pass job_id for logging/context
            # queue='notifications' # Send to specific queue if configured
        )
        logger.info(
            f"Sent task 'send_notification' with ID: {task.id} for job {job_id}"
        )
        return task.id
    except Exception as e:
        logger.error(
            f"Failed to send notification task for job {job_id}, email {email}: {e}",
            exc_info=True,
        )
        raise


# __init__.py should expose celery_app, redis_client, add_transcoding_job etc.
