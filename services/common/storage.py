# ./services/common/storage.py
import os

import boto3
from botocore.exceptions import ClientError

from common import setup_logger  # Assuming logger setup is here

logger = setup_logger()

# --- S3 Client Initialization ---
# Configuration should come from the environment of the service *using* this common code
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # e.g., http://minio:9000 for local
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")  # For MinIO/localstack
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")  # For MinIO/localstack
S3_BUCKET = os.getenv("S3_BUCKET")  # The target bucket name
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")  # Default region if not set

# Create client, handling potential endpoint/credentials
s3_client = None
if S3_BUCKET:  # Only proceed if bucket is configured
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT_URL,  # Will be None if not set (uses default AWS endpoint)
            aws_access_key_id=S3_ACCESS_KEY,  # Will be None if not set (uses default cred chain)
            aws_secret_access_key=S3_SECRET_KEY,  # Will be None if not set
            region_name=AWS_REGION,  # Good practice to specify region
        )
        # Optional: Check connection/credentials early
        # s3_client.list_buckets() # Requires ListAllMyBuckets permission
        logger.info(
            f"S3 client initialized for bucket '{S3_BUCKET}' (Endpoint: {S3_ENDPOINT_URL or 'Default AWS'})"
        )
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}", exc_info=True)
        s3_client = None  # Ensure client is None if init fails
else:
    logger.warning("S3_BUCKET environment variable not set. S3 operations will fail.")


# --- S3 Operations ---


def upload_to_s3(file_obj, s3_key):
    """Uploads a file-like object to the configured S3 bucket."""
    if not s3_client:
        raise ConnectionError("S3 client is not initialized. Check configuration.")
    if not S3_BUCKET:
        raise ValueError("S3_BUCKET is not configured.")

    try:
        # ExtraArgs can be used for metadata, ACLs, etc.
        # ExtraArgs={'ContentType': 'video/mp4'}
        s3_client.upload_fileobj(file_obj, S3_BUCKET, s3_key)
        logger.debug(f"Successfully uploaded to S3 key: {s3_key}")
    except ClientError as e:
        logger.error(f"S3 ClientError during upload to {s3_key}: {e}", exc_info=True)
        raise  # Re-raise the exception for the caller to handle
    except Exception as e:
        logger.error(
            f"Unexpected error during S3 upload to {s3_key}: {e}", exc_info=True
        )
        raise


def download_from_s3(s3_key, file_obj):
    """Downloads an object from S3 into a file-like object."""
    if not s3_client:
        raise ConnectionError("S3 client is not initialized. Check configuration.")
    if not S3_BUCKET:
        raise ValueError("S3_BUCKET is not configured.")

    try:
        s3_client.download_fileobj(S3_BUCKET, s3_key, file_obj)
        logger.debug(f"Successfully downloaded S3 key: {s3_key}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.error(f"S3 object not found: {s3_key}")
            raise FileNotFoundError(f"S3 object not found: {s3_key}") from e
        else:
            logger.error(
                f"S3 ClientError during download from {s3_key}: {e}", exc_info=True
            )
            raise
    except Exception as e:
        logger.error(
            f"Unexpected error during S3 download from {s3_key}: {e}", exc_info=True
        )
        raise


def get_s3_presigned_url(s3_key, expiration=3600):
    """Generates a presigned URL for downloading an S3 object."""
    if not s3_client:
        raise ConnectionError("S3 client is not initialized. Check configuration.")
    if not S3_BUCKET:
        raise ValueError("S3_BUCKET is not configured.")

    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiration,  # URL expiry time in seconds
        )
        logger.debug(f"Generated presigned URL for S3 key: {s3_key}")
        return url
    except ClientError as e:
        logger.error(
            f"S3 ClientError generating presigned URL for {s3_key}: {e}", exc_info=True
        )
        return None  # Return None or raise exception
    except Exception as e:
        logger.error(
            f"Unexpected error generating presigned URL for {s3_key}: {e}",
            exc_info=True,
        )
        return None
