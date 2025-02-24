import smtplib
from email.mime.text import MIMEText

from common import celery, setup_logger

from services.notification_service.config import (
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = setup_logger()


@celery.task
def send_notification(email, download_url):
    msg = MIMEText(f"Your file is ready! Download it here: {download_url}")
    msg["Subject"] = "Transcoding Complete"
    msg["From"] = SMTP_USER
    msg["To"] = email

    try:
        # Making sure SMTP_* environment variables are set in the docker-compose.yml file
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            logger.info(f"Notification sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send notification to {email}: {str(e)}")


if __name__ == "__main__":
    # For testing purposes
    send_notification.delay("test@example.com", "http://example.com/download/test.mp4")
