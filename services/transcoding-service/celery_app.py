# ./services/transcoding-service/celery_app.py
import os
import logging
from celery import Celery
# from dotenv import dotenv_values

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Load .env file from project root
config = {
    # **dotenv_values(".env"),  # load development variables
    **os.environ,  # override loaded values with environment variables
}

# Create Celery instance
celery_app = Celery(
    'transcoding_tasks', # namespace for tasks
    broker=config.get('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=config.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    include=['tasks'] # List of modules to import tasks from (tasks.py)
)

# Optional Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Transcoding can be long-running, consider visibility timeout if using message queues other than Redis
    # broker_transport_options = {'visibility_timeout': 3600} # e.g., 1 hour for SQS
    # Acknowledge task only after completion/failure (requires idempotent tasks or careful handling)
    task_acks_late = True,
    # Process one task at a time per worker process if FFmpeg is resource-heavy
    worker_prefetch_multiplier = 1
    # Set default task time limits if desired
    # task_time_limit = 3600 # Soft time limit (raises SoftTimeLimitExceeded)
    # task_soft_time_limit = 3500 # Hard time limit (kills worker process)
)

logger.info("Transcoding Celery app configured.")
logger.info(f"Broker URL: {celery_app.conf.broker_url}")

# Expose the configured app
app = celery_app