# ./services/common/storage.py
"""
Utility functions for interacting with AWS S3 storage.

Requires AWS credentials to be configured (e.g., via environment variables
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, or via
IAM roles when running on EC2/ECS/Fargate).
"""

import logging
import os
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

# --- Logging ---
# Each service using this module should have its own logger,
# but we can create a logger specific to this module for internal messages.
logger = logging.getLogger(__name__)
# Configure basic logging if this module is run standalone or for testing
# logging.basicConfig(level=logging.INFO)

# --- Configuration ---
# Load from environment variables
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
S3_PRESIGNED_URL_EXPIRATION = int(os.environ.get('PRESIGNED_URL_EXPIRATION', 3600)) # Default 1 hour
AWS_ENDPOINT_URL = os.environ.get('AWS_ENDPOINT_URL') # <-- Get endpoint override

# Boto3 Configuration (optional: for retries, etc.)
# See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
# BOTO_CONFIG = Config(
#     region_name=AWS_REGION,
#     signature_version="s3v4",  # Recommended for S3
#     retries={
#         "max_attempts": 3,  # Number of retry attempts
#         "mode": "standard",  # Retry mode ('standard', 'legacy', 'adaptive')
#     },
# )

BOTO_CONFIG = Config(
    region_name=AWS_REGION,
    signature_version='s3v4',
    retries={'max_attempts': 3, 'mode': 'standard'}
    # Optional: Needed for MinIO path-style access if virtual-host style fails
    # s3={'addressing_style': 'path'} if AWS_ENDPOINT_URL else None
)


# --- Custom Exception ---
class S3Error(Exception):
    """Custom exception for S3 related errors."""

    pass


class S3ConfigError(S3Error):
    """Exception for S3 configuration issues."""

    pass


class S3UploadError(S3Error):
    """Exception for S3 upload failures."""

    pass


class S3DownloadError(S3Error):
    """Exception for S3 download failures."""

    pass


# --- Boto3 S3 Client Initialization ---
s3_client = None
s3_resource = None

# try:
#     if not S3_BUCKET_NAME:
#         logger.error("S3_BUCKET_NAME environment variable is not set.")
#         # Raise configuration error only if used? Or log and let functions fail?
#         # Let's allow initialization but functions will fail if BUCKET_NAME is missing.

#     # Use session to ensure credentials are sourced consistently
#     session = boto3.Session()
#     s3_client = session.client("s3", config=BOTO_CONFIG)
#     s3_resource = session.resource("s3", config=BOTO_CONFIG)
#     logger.info(f"Boto3 S3 client and resource initialized for region {AWS_REGION}.")

#     # Optional: Check credentials early
#     # sts_client = session.client('sts')
#     # identity = sts_client.get_caller_identity()
#     # logger.info(f"Running with AWS identity: {identity['Arn']}")

# except (NoCredentialsError, PartialCredentialsError) as e:
#     logger.error(f"AWS credentials not found or incomplete: {e}")
#     # Services using this module will fail when calling S3 functions
#     s3_client = None
#     s3_resource = None
# except Exception as e:
#     logger.error(f"Error initializing Boto3 S3 client: {e}")
#     s3_client = None
#     s3_resource = None

try:
    # Use session to ensure credentials are sourced consistently
    session = boto3.Session()
    s3_client = session.client(
        's3',
        config=BOTO_CONFIG,
        endpoint_url=AWS_ENDPOINT_URL # <-- Pass endpoint_url if set
    )
    s3_resource = session.resource(
        's3',
        config=BOTO_CONFIG,
        endpoint_url=AWS_ENDPOINT_URL # <-- Pass endpoint_url if set
    )
    if AWS_ENDPOINT_URL:
         logger.info(f"Boto3 S3 client initialized for endpoint {AWS_ENDPOINT_URL}")
    else:
         logger.info(f"Boto3 S3 client initialized for default AWS endpoint in region {AWS_REGION}.")

except (NoCredentialsError, PartialCredentialsError) as e:
    logger.error(f"AWS credentials not found or incomplete: {e}")
except Exception as e:
    logger.error(f"Error initializing Boto3 S3 client: {e}")


# --- S3 Functions ---


def upload_fileobj(
    file_obj, s3_key, Bucket=S3_BUCKET_NAME, ContentType=None, ExtraArgs=None
):
    """
    Uploads a file-like object to an S3 bucket.

    Args:
        file_obj: File-like object (e.g., opened file, BytesIO, Flask file stream).
        s3_key (str): The desired key (path) in the S3 bucket.
        Bucket (str, optional): The target S3 bucket. Defaults to S3_BUCKET_NAME from env.
        ContentType (str, optional): The standard MIME type of the file. If not provided,
                                     boto3 might try to guess or default.
        ExtraArgs (dict, optional): Extra arguments passed to the upload function
                                    (e.g., {'ACL': 'public-read'}, {'Metadata': {...}}).

    Raises:
        S3ConfigError: If S3 client or bucket name is not configured.
        S3UploadError: If the upload fails.
    """
    if not s3_client:
        raise S3ConfigError(
            "S3 client not initialized. Check AWS credentials and configuration."
        )
    if not Bucket:
        raise S3ConfigError("S3 bucket name is not configured.")

    upload_args = ExtraArgs or {}
    if ContentType:
        upload_args["ContentType"] = ContentType

    logger.debug(f"Attempting to upload file object to s3://{Bucket}/{s3_key}")
    try:
        s3_client.upload_fileobj(
            Fileobj=file_obj, Bucket=Bucket, Key=s3_key, ExtraArgs=upload_args
        )
        logger.info(f"Successfully uploaded file object to s3://{Bucket}/{s3_key}")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_msg = e.response.get("Error", {}).get("Message")
        logger.error(
            f"S3 ClientError uploading to {s3_key}: {error_code} - {error_msg}"
        )
        raise S3UploadError(
            f"Failed to upload to S3 ({error_code}): {error_msg}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error uploading file object to {s3_key}: {e}")
        raise S3UploadError(f"Unexpected error during S3 upload: {e}") from e


def upload_file(file_path, s3_key, Bucket=S3_BUCKET_NAME, ExtraArgs=None):
    """
    Uploads a file from the local filesystem to an S3 bucket.

    Args:
        file_path (str): Path to the local file to upload.
        s3_key (str): The desired key (path) in the S3 bucket.
        Bucket (str, optional): The target S3 bucket. Defaults to S3_BUCKET_NAME from env.
        ExtraArgs (dict, optional): Extra arguments like ContentType, Metadata, ACL.
                                    Example: {'ContentType': 'video/mp4'}

    Raises:
        S3ConfigError: If S3 client or bucket name is not configured.
        FileNotFoundError: If the local file_path does not exist.
        S3UploadError: If the upload fails.
    """
    if not s3_client:
        raise S3ConfigError(
            "S3 client not initialized. Check AWS credentials and configuration."
        )
    if not Bucket:
        raise S3ConfigError("S3 bucket name is not configured.")
    if not os.path.exists(file_path):
        logger.error(f"Local file not found for upload: {file_path}")
        raise FileNotFoundError(f"Local file not found: {file_path}")

    upload_args = ExtraArgs or {}

    logger.debug(f"Attempting to upload file {file_path} to s3://{Bucket}/{s3_key}")
    try:
        s3_client.upload_file(
            Filename=file_path, Bucket=Bucket, Key=s3_key, ExtraArgs=upload_args
        )
        logger.info(f"Successfully uploaded {file_path} to s3://{Bucket}/{s3_key}")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_msg = e.response.get("Error", {}).get("Message")
        logger.error(
            f"S3 ClientError uploading {file_path} to {s3_key}: {error_code} - {error_msg}"
        )
        raise S3UploadError(
            f"Failed to upload to S3 ({error_code}): {error_msg}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error uploading {file_path} to {s3_key}: {e}")
        raise S3UploadError(f"Unexpected error during S3 upload: {e}") from e


def download_file(s3_key, local_path, Bucket=S3_BUCKET_NAME):
    """
    Downloads a file from S3 to the local filesystem.

    Args:
        s3_key (str): The key (path) of the file in the S3 bucket.
        local_path (str): The desired local path to save the downloaded file.
        Bucket (str, optional): The source S3 bucket. Defaults to S3_BUCKET_NAME from env.

    Raises:
        S3ConfigError: If S3 resource or bucket name is not configured.
        S3DownloadError: If the download fails (e.g., file not found, permissions).
    """
    if not s3_resource:
        raise S3ConfigError(
            "S3 resource not initialized. Check AWS credentials and configuration."
        )
    if not Bucket:
        raise S3ConfigError("S3 bucket name is not configured.")

    # Ensure local directory exists
    local_dir = os.path.dirname(local_path)
    if local_dir and not os.path.exists(local_dir):
        try:
            os.makedirs(local_dir)
            logger.info(f"Created local directory: {local_dir}")
        except OSError as e:
            logger.error(f"Failed to create local directory {local_dir}: {e}")
            raise S3DownloadError(
                f"Cannot create local directory {local_dir}: {e}"
            ) from e

    logger.debug(f"Attempting to download s3://{Bucket}/{s3_key} to {local_path}")
    try:
        s3_resource.Bucket(Bucket).download_file(s3_key, local_path)
        logger.info(f"Successfully downloaded s3://{Bucket}/{s3_key} to {local_path}")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_msg = e.response.get("Error", {}).get("Message")
        logger.error(f"S3 ClientError downloading {s3_key}: {error_code} - {error_msg}")
        if error_code == "404":
            raise S3DownloadError(
                f"File not found in S3: s3://{Bucket}/{s3_key}"
            ) from e
        elif error_code == "403":
            raise S3DownloadError(
                f"Permission denied accessing S3 file: s3://{Bucket}/{s3_key}"
            ) from e
        else:
            raise S3DownloadError(
                f"Failed to download from S3 ({error_code}): {error_msg}"
            ) from e
    except Exception as e:
        logger.error(f"Unexpected error downloading {s3_key}: {e}")
        raise S3DownloadError(f"Unexpected error during S3 download: {e}") from e


def create_presigned_url(
    s3_key,
    Bucket=S3_BUCKET_NAME,
    expiration=S3_PRESIGNED_URL_EXPIRATION,
    http_method="GET",
):
    """
    Generates a pre-signed URL for an S3 object.

    Args:
        s3_key (str): The key (path) of the object in S3.
        Bucket (str, optional): The S3 bucket. Defaults to S3_BUCKET_NAME from env.
        expiration (int, optional): Time in seconds for the URL to remain valid.
                                    Defaults to S3_PRESIGNED_URL_EXPIRATION from env.
        http_method (str, optional): The HTTP method allowed (e.g., 'GET', 'PUT').
                                     Defaults to 'GET'.

    Returns:
        str: The pre-signed URL, or None if generation fails.

    Raises:
        S3ConfigError: If S3 client or bucket name is not configured.
        S3Error: If URL generation fails.
    """
    if not s3_client:
        raise S3ConfigError(
            "S3 client not initialized. Check AWS credentials and configuration."
        )
    if not Bucket:
        raise S3ConfigError("S3 bucket name is not configured.")

    # Map HTTP method to the correct boto3 client method name
    method_map = {
        "GET": "get_object",
        "PUT": "put_object",
        # Add 'POST', 'DELETE' if needed
    }
    client_method = method_map.get(http_method.upper())
    if not client_method:
        raise ValueError(f"Unsupported HTTP method for pre-signed URL: {http_method}")

    params = {"Bucket": Bucket, "Key": s3_key}
    # Add specific parameters if needed for methods like PUT (e.g., ContentType)

    logger.debug(f"Generating pre-signed URL for {http_method} s3://{Bucket}/{s3_key}")
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod=client_method,
            Params=params,
            ExpiresIn=expiration,
            HttpMethod=http_method.upper(),
        )
        logger.info(f"Successfully generated pre-signed URL for {s3_key}")
        return url
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_msg = e.response.get("Error", {}).get("Message")
        logger.error(
            f"S3 ClientError generating pre-signed URL for {s3_key}: {error_code} - {error_msg}"
        )
        raise S3Error(
            f"Failed to generate pre-signed URL ({error_code}): {error_msg}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error generating pre-signed URL for {s3_key}: {e}")
        raise S3Error(f"Unexpected error during pre-signed URL generation: {e}") from e


# --- Example Usage (for testing) ---
if __name__ == "__main__":
    # This block runs only when storage.py is executed directly
    print("Common Storage Module - Example Usage")
    logging.basicConfig(level=logging.INFO)

    if not S3_BUCKET_NAME:
        print("Please set the S3_BUCKET_NAME environment variable for testing.")
    else:
        TEST_KEY = "common-storage-test.txt"
        TEST_FILE = "common_storage_test_local.txt"
        TEST_CONTENT = f"Hello from common.storage test at {time.time()}!"

        try:
            # 1. Upload file object
            import io

            file_obj = io.BytesIO(TEST_CONTENT.encode("utf-8"))
            print(f"\n1. Uploading file object to s3://{S3_BUCKET_NAME}/{TEST_KEY}")
            upload_fileobj(file_obj, TEST_KEY, ContentType="text/plain")

            # 2. Download file
            print(f"\n2. Downloading s3://{S3_BUCKET_NAME}/{TEST_KEY} to {TEST_FILE}")
            download_file(TEST_KEY, TEST_FILE)
            with open(TEST_FILE, "r") as f:
                content = f.read()
                print(
                    f"   Downloaded content matches original: {content == TEST_CONTENT}"
                )
            os.remove(TEST_FILE)  # Clean up local file

            # 3. Generate pre-signed URL
            print(
                f"\n3. Generating pre-signed GET URL for s3://{S3_BUCKET_NAME}/{TEST_KEY}"
            )
            url = create_presigned_url(TEST_KEY, expiration=60)  # 60 seconds expiry
            print(f"   URL (valid for 60s): {url}")

            # 4. Upload local file (as alternative test)
            # with open(TEST_FILE, 'w') as f: f.write("Local file upload test.")
            # print(f"\n4. Uploading local file {TEST_FILE} to {TEST_KEY}")
            # upload_file(TEST_FILE, TEST_KEY)
            # os.remove(TEST_FILE)

        except (S3Error, FileNotFoundError, Exception) as e:
            print("\n--- TEST FAILED ---")
            print(f"An error occurred: {e}")

        finally:
            # Optional: Clean up test object from S3
            try:
                if s3_client:
                    print(f"\nCleaning up s3://{S3_BUCKET_NAME}/{TEST_KEY}")
                    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=TEST_KEY)
            except Exception as cleanup_e:
                print(f"Error during S3 cleanup: {cleanup_e}")
