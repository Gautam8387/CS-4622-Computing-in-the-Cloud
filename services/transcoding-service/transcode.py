# ./services/transcoding-service/transcode.py
import os
import subprocess
import time

# Import the shared Celery app instance from common
from common import (
    celery_app,
    download_from_s3,
    get_s3_presigned_url,
    redis_client,
    send_notification_job,
    setup_logger,
    upload_to_s3,
)

# Load configuration specific to this service
from .config import (
    AUDIO_CODECS,
    FFMPEG_CMD_AUDIO_FROM_AUDIO,
    FFMPEG_CMD_AUDIO_FROM_VIDEO,
    FFMPEG_CMD_VIDEO,
    TEMP_DIR,
)

logger = setup_logger()

# --- Helper Functions ---


def update_job_progress(job_id, status, download_url=None, error_message=None):
    """Updates job status and potentially URL/error in Redis Hash."""
    if not redis_client:
        logger.error(f"Redis client not available, cannot update progress for {job_id}")
        return
    try:
        job_key = f"job:{job_id}"
        update_data = {"status": status.lower()}
        if download_url:
            update_data["download_url"] = download_url
        if error_message:
            # Limit error message length if necessary
            update_data["error"] = str(error_message)[:1024]

        redis_client.hset(job_key, mapping=update_data)
        logger.debug(f"Updated job {job_id} status to {status}")
    except Exception as e:
        logger.error(
            f"Failed to update Redis progress for job {job_id}: {e}", exc_info=True
        )


# --- Celery Task Definition ---


@celery_app.task(
    bind=True, name="transcode_file", max_retries=1, default_retry_delay=60
)
def transcode_file(self, original_filename, s3_key, email, output_format):
    """
    Celery task to download, transcode using FFmpeg, and upload the result.
    'bind=True' allows accessing task instance via 'self'.
    """
    job_id = self.request.id
    logger.info(
        f"Starting transcoding job {job_id} for {s3_key} to {output_format} for {email}"
    )
    update_job_progress(job_id, "processing")  # Update status in Redis

    local_input_path = None
    local_output_path = None

    try:
        # --- Prepare file paths ---
        base_filename = original_filename.rsplit(".", 1)[0]
        # Use job_id to ensure unique temp filenames
        temp_input_filename = f"{job_id}_{original_filename}"
        temp_output_filename = f"{job_id}_{base_filename}.{output_format}"

        local_input_path = os.path.join(TEMP_DIR, temp_input_filename)
        local_output_path = os.path.join(TEMP_DIR, temp_output_filename)
        output_s3_key = f"processed/{temp_output_filename}"  # Store with unique name

        # Create temp dir if it doesn't exist
        os.makedirs(TEMP_DIR, exist_ok=True)

        # --- Download Input File ---
        logger.info(f"Downloading {s3_key} to {local_input_path} for job {job_id}")
        start_download = time.time()
        with open(local_input_path, "wb") as f:
            download_from_s3(s3_key, f)
        download_duration = time.time() - start_download
        logger.info(f"Downloaded {s3_key} in {download_duration:.2f}s for job {job_id}")

        # --- Determine Input Type ---
        # Basic check, could use ffprobe for more accuracy if needed
        input_ext = (
            original_filename.rsplit(".", 1)[-1].lower()
            if "." in original_filename
            else ""
        )
        # Crude assumption based on common extensions
        is_video_input = input_ext in ["mp4", "avi", "mov", "mkv", "webm", "flv", "wmv"]
        is_audio_input = input_ext in ["mp3", "wav", "flac", "aac", "ogg", "m4a"]

        # --- Build FFmpeg Command ---
        is_audio_output = output_format in AUDIO_CODECS

        if is_audio_output:
            if output_format not in AUDIO_CODECS:
                raise ValueError(f"Unsupported audio output format: {output_format}")
            codec_info = AUDIO_CODECS[output_format]
            if is_video_input:  # Extract audio from video
                cmd_template = FFMPEG_CMD_AUDIO_FROM_VIDEO
                cmd = cmd_template.format(
                    input=local_input_path,
                    codec=codec_info["codec"],
                    bitrate=f"{codec_info['bitrate']}"
                    if codec_info.get("bitrate")
                    else "",  # Add -b:a only if bitrate exists
                    output=local_output_path,
                ).split()
                # Remove empty strings resulting from formatting if bitrate is None
                cmd = [part for part in cmd if part]
            elif is_audio_input:  # Convert audio to audio
                cmd_template = FFMPEG_CMD_AUDIO_FROM_AUDIO
                cmd = cmd_template.format(
                    input=local_input_path,
                    codec=codec_info["codec"],
                    bitrate=f"{codec_info['bitrate']}"
                    if codec_info.get("bitrate")
                    else "",
                    output=local_output_path,
                ).split()
                cmd = [part for part in cmd if part]
            else:
                raise ValueError(
                    "Cannot determine input type (video/audio) for audio conversion."
                )
        else:  # Video output (assuming mp4, webm etc handled by the template)
            cmd_template = FFMPEG_CMD_VIDEO
            cmd = cmd_template.format(
                input=local_input_path, output=local_output_path
            ).split()

        logger.info(f"Executing FFmpeg command for job {job_id}: {' '.join(cmd)}")

        # --- Execute FFmpeg ---
        start_ffmpeg = time.time()
        # Use subprocess.run for better control and error capture
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )  # check=False to handle errors manually
        ffmpeg_duration = time.time() - start_ffmpeg

        if result.returncode != 0:
            # Log FFmpeg errors
            error_output = (
                result.stderr or result.stdout
            )  # FFmpeg often outputs errors to stdout too
            logger.error(
                f"FFmpeg failed for job {job_id}. Return Code: {result.returncode}"
            )
            logger.error(f"FFmpeg Output:\n{error_output}")
            raise Exception(
                f"FFmpeg failed: {error_output[:500]}"
            )  # Raise exception to trigger Celery retry/failure

        logger.info(
            f"FFmpeg completed successfully in {ffmpeg_duration:.2f}s for job {job_id}"
        )

        # --- Upload Output File ---
        logger.info(
            f"Uploading {local_output_path} to {output_s3_key} for job {job_id}"
        )
        start_upload = time.time()
        with open(local_output_path, "rb") as f:
            upload_to_s3(f, output_s3_key)
        upload_duration = time.time() - start_upload
        logger.info(
            f"Uploaded {output_s3_key} in {upload_duration:.2f}s for job {job_id}"
        )

        # --- Generate Presigned URL ---
        download_url = get_s3_presigned_url(
            output_s3_key, expiration=3600 * 24 * 2
        )  # e.g., valid for 48 hours
        if not download_url:
            logger.warning(
                f"Could not generate download URL for {output_s3_key}, job {job_id}"
            )
            # Proceed without URL, but log warning

        # --- Send Notification ---
        send_notification_job(email, download_url, job_id)  # Pass job_id for context

        # --- Update Final Status in Redis ---
        update_job_progress(job_id, "completed", download_url=download_url)

        # --- Schedule Archiving (Optional) ---
        # archive_eta = datetime.now(timezone.utc) + timedelta(hours=ARCHIVE_DELAY_HOURS)
        # archive_file.apply_async(args=[output_s3_key], eta=archive_eta)
        # logger.info(f"Scheduled archiving for {output_s3_key} at {archive_eta} for job {job_id}")

        logger.info(f"Successfully completed transcoding job {job_id}")
        return {
            "status": "completed",
            "output_url": download_url,
            "output_s3_key": output_s3_key,
        }

    except FileNotFoundError as e:
        logger.error(f"Input file not found for job {job_id}: {e}", exc_info=True)
        update_job_progress(job_id, "failed", error_message=f"Input file error: {e}")
        # Don't retry if input file is missing

    except Exception as e:
        logger.error(f"Error during transcoding job {job_id}: {e}", exc_info=True)
        error_msg = f"Transcoding failed: {e}"
        update_job_progress(job_id, "failed", error_message=error_msg)
        try:
            # Retry the task if max_retries not exceeded
            logger.warning(f"Retrying job {job_id} due to error: {e}")
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Job {job_id} failed after max retries.")
            # Optionally send failure notification here
    finally:
        # --- Cleanup Temporary Files ---
        try:
            if local_input_path and os.path.exists(local_input_path):
                os.remove(local_input_path)
                logger.debug(f"Cleaned up temporary input file: {local_input_path}")
            if local_output_path and os.path.exists(local_output_path):
                os.remove(local_output_path)
                logger.debug(f"Cleaned up temporary output file: {local_output_path}")
        except OSError as e:
            logger.warning(
                f"Error cleaning up temporary files for job {job_id}: {e}",
                exc_info=True,
            )


@celery_app.task(name="archive_file")
def archive_file(s3_key):
    """Placeholder task for moving file to cold storage (Glacier)."""
    # In a real AWS environment, this would involve:
    # 1. Copying the object to the same key with STORAGE_CLASS='GLACIER' or 'DEEP_ARCHIVE'
    #    s3_client.copy_object(Bucket=S3_BUCKET, Key=s3_key, CopySource={'Bucket': S3_BUCKET, 'Key': s3_key}, StorageClass='GLACIER')
    # 2. Optionally deleting the original standard storage object if the copy replaces it.
    #    (Lifecycle rules are generally preferred over manual deletion/copying)
    logger.info(f"Simulating archive (move to cold storage) for S3 key: {s3_key}")
    # For MinIO/local testing, this task does nothing significant.
    # Could potentially delete the file to simulate removal from hot storage.
    # try:
    #     delete_from_s3(s3_key) # Assuming a delete function exists in common.storage
    #     logger.info(f"Deleted {s3_key} from hot storage (simulated archive).")
    # except Exception as e:
    #     logger.error(f"Error deleting {s3_key} during simulated archive: {e}")


# Note: Ensure the Celery worker running this service has FFmpeg installed (handled in Dockerfile)
# and appropriate access to S3 and Redis.
