# ./services/notification-service/tasks.py
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from botocore.exceptions import ClientError
from celery import shared_task

# Important: Need access to common utilities. Assumes 'common' is in Python path.
# This might require adjusting PYTHONPATH in Dockerfile or how 'common' is included.
try:
    from common import storage
except ImportError:
    # Fallback if running locally without proper path setup - adjust as needed
    import sys

    # Assuming 'services' is the parent directory
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from common import storage


# Get Logger instance defined in celery_app.py or create a new one
logger = logging.getLogger(__name__)

# SMTP Configuration (from environment variables loaded by celery_app)
MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))  # Default to 587
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ["true", "1", "t"]
MAIL_SENDER_EMAIL = os.environ.get(
    "MAIL_SENDER_EMAIL", MAIL_USERNAME
)  # Default sender to username if not set
MAIL_SENDER_NAME = os.environ.get("MAIL_SENDER_NAME", "Media Transcoder")  # App name

# Check if SMTP is configured
SMTP_CONFIGURED = all([MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD])

if not SMTP_CONFIGURED:
    logger.warning(
        "SMTP is not fully configured. Email notifications will be disabled."
    )
    # Alternatively, you could configure to use AWS SES API via Boto3 here
    # SES_SENDER_EMAIL = os.environ.get('SES_SENDER_EMAIL')
    # SES_CONFIGURED = SES_SENDER_EMAIL is not None


@shared_task(bind=True, name='notification.tasks.send_notification_email', max_retries=3, default_retry_delay=60)
def send_notification_email(self, payload):
    """
    Celery task to generate a pre-signed URL and send a notification email.

    Args:
        payload (dict): A dictionary containing job details:
            - job_id (str): The unique ID of the job.
            - notification_email (str): The email address to send the notification to.
            - original_filename (str): The original name of the uploaded file.
            - output_format (str): The target format.
            - output_s3_key (str): The S3 key of the processed file.
    """
    job_id = payload.get("job_id")
    recipient_email = payload.get("notification_email")
    original_filename = payload.get("original_filename", "your file")
    output_format = payload.get("output_format", "unknown format")
    output_s3_key = payload.get("output_s3_key")

    if not recipient_email:
        logger.warning(
            f"Job {job_id}: No recipient email provided. Skipping notification."
        )
        return {"status": "skipped", "reason": "No recipient email"}

    if not output_s3_key:
        logger.error(
            f"Job {job_id}: Missing 'output_s3_key' in payload for notification."
        )
        # Don't retry if data is missing
        return {"status": "failed", "reason": "Missing S3 key"}

    logger.info(
        f"Job {job_id}: Preparing notification email for {recipient_email} for file '{original_filename}' -> '{output_format}'"
    )

    # 1. Generate Pre-signed URL
    try:
        # Use the common storage utility function
        download_url = storage.create_presigned_url(output_s3_key)
        if not download_url:
            raise ValueError("Pre-signed URL generation returned None")
        logger.info(
            f"Job {job_id}: Generated download URL: {download_url[:100]}..."
        )  # Log truncated URL
    except (ClientError, ValueError, Exception) as e:
        logger.error(
            f"Job {job_id}: Failed to generate pre-signed URL for {output_s3_key}: {e}"
        )
        # Retry might help if it's a temporary AWS issue
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "reason": f"Failed to generate URL after retries: {e}",
            }
        except Exception as retry_exc:  # Catch potential errors during retry itself
            logger.error(
                f"Job {job_id}: Error during retry mechanism for URL generation: {retry_exc}"
            )
            return {
                "status": "failed",
                "reason": f"Error during retry mechanism for URL generation: {retry_exc}",
            }

    # 2. Construct and Send Email (Using SMTP)
    if not SMTP_CONFIGURED:
        logger.warning(
            f"Job {job_id}: SMTP not configured, cannot send email notification."
        )
        return {"status": "skipped", "reason": "SMTP not configured"}

    subject = f"Your Media Transcoding Job is Complete! ({original_filename})"
    # Construct email body (consider using HTML for better formatting)
    body_text = f"""
Hello,

Your media transcoding job for the file '{original_filename}' (Job ID: {job_id}) is complete.

The file has been converted to {output_format.upper()} format.

You can download the processed file using the link below. Please note this link will expire.

{download_url}

Thank you for using the Media Transcoding Service!
    """
    body_html = f"""
<html>
<body>
    <p>Hello,</p>
    <p>Your media transcoding job for the file '<b>{original_filename}</b>' (Job ID: {job_id}) is complete.</p>
    <p>The file has been converted to <b>{output_format.upper()}</b> format.</p>
    <p>You can download the processed file using the link below. Please note this link will expire.</p>
    <p><a href="{download_url}"><b>Download Processed File</b></a></p>
    <p><i>If the link doesn't work, please copy and paste the following URL into your browser:</i><br>{download_url}</p>
    <p>Thank you for using the Media Transcoding Service!</p>
</body>
</html>
    """

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{MAIL_SENDER_NAME} <{MAIL_SENDER_EMAIL}>"
    message["To"] = recipient_email

    # Attach both plain text and HTML versions
    part1 = MIMEText(body_text, "plain")
    part2 = MIMEText(body_html, "html")
    message.attach(part1)
    message.attach(part2)

    try:
        logger.info(
            f"Job {job_id}: Connecting to SMTP server {MAIL_SERVER}:{MAIL_PORT}"
        )
        if MAIL_USE_TLS:
            # Use SMTP_SSL for implicit TLS (port 465 usually) or starttls for explicit TLS (port 587 usually)
            # Assuming explicit TLS for port 587
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=30)
            server.ehlo()  # Identify ourselves to the SMTP server
            server.starttls()  # Secure the connection
            server.ehlo()  # Re-identify ourselves over the secure connection
        else:
            # Use basic SMTP (less secure, port 25 usually)
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=30)

        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        logger.info(f"Job {job_id}: Sending email to {recipient_email}")
        server.sendmail(MAIL_SENDER_EMAIL, recipient_email, message.as_string())
        logger.info(f"Job {job_id}: Email sent successfully to {recipient_email}.")
        server.quit()
        return {"status": "success", "recipient": recipient_email}

    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"Job {job_id}: SMTP Authentication failed for user {MAIL_USERNAME}: {e}"
        )
        # Don't retry on auth errors, likely config issue
        return {
            "status": "failed",
            "reason": f"SMTP Authentication Failed: {e.smtp_code} {e.smtp_error}",
        }
    except smtplib.SMTPException as e:
        logger.error(f"Job {job_id}: Failed to send email via SMTP: {e}")
        # Retry for general SMTP errors (temporary connection issues, etc.)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "reason": f"Failed to send email after retries: {e}",
            }
        except Exception as retry_exc:  # Catch potential errors during retry itself
            logger.error(
                f"Job {job_id}: Error during retry mechanism for email sending: {retry_exc}"
            )
            return {
                "status": "failed",
                "reason": f"Error during retry mechanism for email sending: {retry_exc}",
            }
    except Exception as e:
        logger.exception(
            f"Job {job_id}: An unexpected error occurred during email sending: {e}"
        )
        # Retry for unexpected errors
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "reason": f"Failed after retries due to unexpected error: {e}",
            }
        except Exception as retry_exc:  # Catch potential errors during retry itself
            logger.error(
                f"Job {job_id}: Error during retry mechanism for unexpected error: {retry_exc}"
            )
            return {
                "status": "failed",
                "reason": f"Error during retry mechanism for unexpected error: {retry_exc}",
            }


# Optional: Define more tasks if needed (e.g., notification on failure)
