import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "fallback-user")  # Add email address for fallback
SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD", "fallback-password"
)  # Add email password for fallback
