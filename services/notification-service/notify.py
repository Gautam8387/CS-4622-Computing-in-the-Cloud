# ./services/notification-service/notify.py
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Import the shared Celery app instance and logger
from common import celery_app, setup_logger

# Load configuration for this service
from .config import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USE_TLS, SMTP_USER

logger = setup_logger()

# --- Celery Task Definition ---


@celery_app.task(
    bind=True, name="send_notification", max_retries=3, default_retry_delay=300
)  # Retry after 5 mins
def send_notification(self, email, download_url, job_id):
    """
    Celery task to send an email notification upon job completion.
    """
    logger.info(
        f"Preparing notification for job {job_id} to {email}. URL: {download_url}"
    )

    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        logger.error(f"SMTP settings incomplete for job {job_id}. Cannot send email.")
        # Don't retry if config is missing
        return {"status": "failed", "error": "SMTP configuration incomplete"}

    subject = "Media Transcoding Complete!"
    sender_email = SMTP_USER
    receiver_email = email

    # Create the email message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = receiver_email

    # Create HTML and plain text versions
    text = f"""
Hi there,

Your media file transcoding (Job ID: {job_id}) is complete!

You can download your converted file using the link below (valid for 48 hours):
{download_url}

Thank you for using our service!
    """

    html = f"""
<html>
  <body>
    <p>Hi there,</p>
    <p>Your media file transcoding (Job ID: {job_id}) is complete!</p>
    <p>You can download your converted file using the link below (valid for 48 hours):<br>
      <a href="{download_url}">Download File</a>
    </p>
    <p>If the link above doesn't work, copy and paste this URL into your browser:<br>
       <code>{download_url}</code>
    </p>
    <p>Thank you for using our service!</p>
  </body>
</html>
    """

    # Attach parts to MIMEMultipart message
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    message.attach(part1)
    message.attach(part2)

    try:
        logger.debug(
            f"Connecting to SMTP server {SMTP_HOST}:{SMTP_PORT} for job {job_id}"
        )
        # Establish connection based on TLS setting
        if SMTP_USE_TLS:
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo()  # Can be omitted
                server.starttls(context=context)
                server.ehlo()  # Can be omitted
                logger.debug(
                    f"Logging into SMTP server as {SMTP_USER} for job {job_id}"
                )
                server.login(SMTP_USER, SMTP_PASSWORD)
                logger.debug(f"Sending email to {receiver_email} for job {job_id}")
                server.sendmail(sender_email, receiver_email, message.as_string())
        else:  # Plain SMTP (less common, might be used for local test servers)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                logger.debug(
                    f"Logging into SMTP server as {SMTP_USER} for job {job_id} (no TLS)"
                )
                # Login might be needed depending on server config
                # server.login(SMTP_USER, SMTP_PASSWORD)
                logger.debug(
                    f"Sending email to {receiver_email} for job {job_id} (no TLS)"
                )
                server.sendmail(sender_email, receiver_email, message.as_string())

        logger.info(
            f"Successfully sent notification email to {receiver_email} for job {job_id}"
        )
        return {"status": "sent"}

    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"SMTP Authentication failed for {SMTP_USER} on job {job_id}: {e}",
            exc_info=True,
        )
        # Don't retry on auth errors
        return {"status": "failed", "error": "SMTP Authentication Error"}
    except Exception as e:
        logger.error(
            f"Failed to send notification email for job {job_id} to {email}: {e}",
            exc_info=True,
        )
        try:
            # Retry the task for transient errors (e.g., connection issues)
            logger.warning(f"Retrying notification for job {job_id} due to error: {e}")
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Notification failed after max retries for job {job_id}.")
            # Optionally update job status in Redis to indicate notification failure
            return {"status": "failed", "error": "Max retries exceeded"}


# Note: Ensure the Celery worker running this service has network access to the SMTP server.
