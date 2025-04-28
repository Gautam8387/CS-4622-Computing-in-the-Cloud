# ./services/notification-service/config.py
import os

from dotenv import load_dotenv

load_dotenv()

# Celery configuration (can also be set via environment in docker-compose)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)  # Optional for worker

# SMTP Configuration (Essential for this service)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))  # Default to 587 (TLS)
SMTP_USER = os.getenv("SMTP_USER")  # Sending email address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # App password or regular password
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True").lower() in [
    "true",
    "1",
    "yes",
]  # Default to TLS

# Check essential SMTP config
if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
    print(
        "Warning: Notification Service SMTP settings (HOST, USER, PASSWORD) are not fully configured."
    )

# Optional: Specify queue name if worker should listen only to specific queue
CELERY_QUEUE_NAME = os.getenv("CELERY_QUEUE_NAME", "celery")  # Default celery queue
