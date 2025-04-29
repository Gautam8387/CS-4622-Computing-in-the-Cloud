# ./services/notification-service/celery_app.py
import logging
import os

from celery import Celery
# from dotenv import dotenv_values

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Load .env file from project root
# Important: Celery workers need access to the same config as the services sending tasks
config = {
    # **dotenv_values(".env"),  # load development variables
    **os.environ,  # override loaded values with environment variables
}

# Create Celery instance
celery_app = Celery(
    "notification_tasks",  # namespace for tasks
    broker=config.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=config.get(
        "CELERY_RESULT_BACKEND", "redis://redis:6379/0"
    ),  # Needed for task state/results if checked
    include=["tasks"],  # List of modules to import tasks from (tasks.py in this case)
)

# Optional Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Add retry settings if needed
    # task_acks_late = True # Consider if tasks are idempotent and long-running
    # worker_prefetch_multiplier = 1 # Process one message at a time if tasks are resource-intensive
)

logger.info("Notification Celery app configured.")
logger.info(f"Broker URL: {celery_app.conf.broker_url}")

# Expose the configured app
app = celery_app

# Note: The actual worker process is started via the command line, e.g.,
# celery -A celery_app worker --loglevel=info
