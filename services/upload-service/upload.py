# ./services/upload-service/upload.py
from common import setup_logger, upload_to_s3  # Import common S3 upload
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_pyfile("config.py")  # Load config (S3 settings)
logger = setup_logger()


@app.route("/upload", methods=["POST"])
def upload():
    """Handles file upload and stores it in S3 raw bucket."""
    if "file" not in request.files:
        logger.warning("Upload attempt with no file part.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    if file.filename == "":
        logger.warning("Upload attempt with no selected file.")
        return jsonify({"error": "No file selected"}), 400

    # Secure the filename provided by the user
    original_filename = secure_filename(file.filename)

    # Optional: Generate a unique name to avoid collisions
    # unique_id = uuid.uuid4()
    # filename = f"{unique_id}_{original_filename}"
    filename = original_filename  # Using original secure name for simplicity now

    s3_key = f"raw/{filename}"  # Store in 'raw/' prefix

    try:
        logger.info(f"Attempting to upload '{original_filename}' to S3 key: {s3_key}")
        # common.upload_to_s3 expects a file-like object and the key
        upload_to_s3(file.stream, s3_key)  # Pass file.stream directly
        logger.info(f"Successfully uploaded '{original_filename}' to S3 as {s3_key}")
        # Return the key so the gateway can use it
        return jsonify({"message": "File uploaded successfully", "s3_key": s3_key}), 200
    except Exception as e:
        # Catch potential Boto3 errors or other exceptions
        logger.error(f"S3 upload failed for key {s3_key}: {e}", exc_info=True)
        # Provide a generic error message to the client
        return jsonify({"error": "Failed to store uploaded file."}), 500


@app.route("/health")
def health_check():
    # Basic health check endpoint
    # Could add a check for S3 credentials/bucket access if needed
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    # Runs on port 5002
    app.run(host="0.0.0.0", port=5002, debug=app.config["DEBUG"])
