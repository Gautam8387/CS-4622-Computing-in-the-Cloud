# ./client/app.py
import time
import secrets
import logging # Ensure logging is imported
from mimetypes import guess_type

import requests
from authlib.integrations.flask_client import OAuth
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
# Load configuration from config.py
app.config.from_pyfile("config.py")

# --- OAuth Setup ---
oauth = OAuth(app)

# Google OAuth Config
google = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# GitHub OAuth Config
github = oauth.register(
    name="github",
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email read:user"},  # Request email scope
)

# --- Routes ---


@app.route("/")
def index():
    user_info = session.get("user_info")
    # Fetch jobs only if logged in (and not in standalone)
    jobs = []
    if user_info and not app.config["STANDALONE_MODE"]:
        jobs = get_user_jobs()

    if app.config["STANDALONE_MODE"] and not user_info:
        # Provide mock user for standalone testing if needed
        session["user_info"] = {"email": "test@example.com", "name": "Test User"}
        user_info = session.get("user_info")

    if app.config["STANDALONE_MODE"] and not jobs:
        jobs = get_mock_jobs()  # Show mock jobs in standalone

    return render_template("index.html", user=user_info, jobs=jobs)



@app.route("/login/<provider>")
def login(provider):
    """Redirects to the OAuth provider for authentication."""
    try:
        oauth_provider = getattr(oauth, provider)
    except AttributeError:
        app.logger.error(f"Attempted to login with unconfigured provider: {provider}")
        flash(f"Error: Login provider '{provider}' is not configured or enabled.", "error")
        return redirect(url_for("index"))

    try:
        redirect_uri = url_for('callback', _external=True)
        app.logger.info(f"Generated Redirect URI for {provider}: '{redirect_uri}'")
    except Exception as e:
        app.logger.error(f"Error generating callback URL for 'callback' route: {e}")
        flash(f"Internal server error generating redirect.", "error")
        return redirect(url_for("index"))

    # --- Generate and Store State & Nonce ---
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16) # Generate nonce
    session['oauth_state'] = state # Store state in session for CSRF
    session['oauth_nonce'] = nonce # Store nonce in session for OIDC
    app.logger.debug(f"Generated OAuth state: {state}")
    app.logger.debug(f"Generated OAuth nonce: {nonce}")
    # --------------------------------------

    # Pass state AND nonce to the authorization redirect
    # Note: Nonce is primarily for OpenID Connect (like Google)
    if provider == 'google':
        return oauth_provider.authorize_redirect(redirect_uri, state=state, nonce=nonce)
    else: # GitHub doesn't typically use nonce in basic OAuth2
        return oauth_provider.authorize_redirect(redirect_uri, state=state)



@app.route("/callback")
def callback():
    """Handles the callback from the OAuth provider."""

    # --- State Validation (CSRF Protection) ---
    received_state = request.args.get('state')
    expected_state = session.pop('oauth_state', None)
    expected_nonce = session.pop('oauth_nonce', None) # Also retrieve nonce

    if not expected_state or received_state != expected_state:
        app.logger.warning("Invalid OAuth state received.")
        flash("Authentication failed due to invalid state (CSRF protection). Please try again.", "error")
        return redirect(url_for('index'))
    app.logger.debug(f"Received valid OAuth state: {received_state}")
    # -----------------------------------------

    # Determine provider (logic might need refinement)
    provider_name = "google"
    # Check referrer or other clues if needed
    if request.referrer and 'github.com' in request.referrer:
         provider_name = "github"
    # If provider was part of state, you could use that too

    try:
        oauth_provider = getattr(oauth, provider_name)
        app.logger.info(f"Handling callback for provider: {provider_name}")

        token = oauth_provider.authorize_access_token()
        app.logger.debug(f"Received provider token for {provider_name}")

        # --- Exchange provider token for our JWT ---
        auth_service_url = app.config["AUTH_SERVICE_URL"]
        exchange_url = f"{auth_service_url}/auth/token"
        payload = {
            "provider": provider_name,
            "token": token,
            "nonce": expected_nonce # --- Pass the nonce to auth-service ---
        }
        app.logger.info(f"Exchanging token with Auth Service: {exchange_url}")
        response = requests.post(exchange_url, json=payload)
        app.logger.debug(f"Auth Service response status: {response.status_code}")
        response.raise_for_status()

        jwt_data = response.json()
        app.logger.debug(f"Received JWT data from Auth Service")

        session["jwt_token"] = jwt_data["token"]
        session["user_info"] = jwt_data["user"]
        app.logger.info(f"User '{jwt_data['user'].get('email')}' successfully logged in via {provider_name}.")
        flash(f"Login via {provider_name.capitalize()} successful!", "success")

    except Exception as e:
        app.logger.error(f"OAuth Callback Error ({provider_name}): {e}", exc_info=True)
        flash(f"Authentication via {provider_name.capitalize()} failed. Please try again or contact support.", "error")

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    """Logs the user out by clearing the session."""
    user_email = session.get("user_info", {}).get('email', 'Unknown User')
    # Optional: Call auth service to invalidate JWT if blocklisting is implemented
    session.pop("jwt_token", None)
    session.pop("user_info", None)
    app.logger.info(f"User '{user_email}' logged out.")
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles file upload requests."""
    # --- Authentication Check ---
    jwt_token = session.get("jwt_token")
    if not jwt_token and not app.config["STANDALONE_MODE"]:
        app.logger.warning("Upload attempt failed: Authentication required.")
        return jsonify({"error": "Authentication required"}), 401

    # --- File and Form Data Validation ---
    if "file" not in request.files:
        app.logger.warning("Upload attempt failed: No file part in request.")
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    email_form = request.form.get("email")  # Email from form (might not be needed)
    output_format = request.form.get("output_format")

    # Get user email from session (preferred source)
    user_info = session.get("user_info")
    email = user_info.get("email") if user_info else email_form

    if not file or file.filename == "":
      app.logger.warning("Upload attempt failed: No file selected.")
      return jsonify({"error": "No file selected"}), 400
    if not email:
      app.logger.warning("Upload attempt failed: Email missing.")
      return jsonify({"error": "User email not found"}), 400 # Should not happen if logged in
    if not output_format:
      app.logger.warning("Upload attempt failed: Output format missing.")
      return jsonify({"error": "Output format is required"}), 400

    app.logger.info(f"Upload received for user '{email}', filename '{file.filename}', format '{output_format}'")

    # --- File Type Validation ---
    mime_type, _ = guess_type(file.filename)
    file_type = "unknown"
    if mime_type:
        if mime_type.startswith("video/"):
            file_type = "video"
        elif mime_type.startswith("audio/"):
            file_type = "audio"

    if file_type == "unknown":
        app.logger.warning(f"Upload failed for user '{email}': Unsupported file type '{mime_type or 'none'}'.")
        return jsonify({"error": f"Unsupported file type: {mime_type or 'Could not determine'}"}), 400

    # --- Format Validation ---
    valid_formats = app.config["VIDEO_FORMATS"].union(app.config["AUDIO_FORMATS"])
    is_video_format = output_format in app.config["VIDEO_FORMATS"]
    is_audio_format = output_format in app.config["AUDIO_FORMATS"]

    if file_type == "video" and not (is_video_format or is_audio_format): # Video can be converted to audio
         app.logger.warning(f"Upload failed for user '{email}': Invalid output format '{output_format}' for video input.")
         return jsonify({"error": f"Invalid output format '{output_format}' for video file."}), 400
    if file_type == "audio" and not is_audio_format:
         app.logger.warning(f"Upload failed for user '{email}': Invalid output format '{output_format}' for audio input.")
         return jsonify({"error": f"Invalid output format '{output_format}' for audio file."}), 400

    # --- Standalone Mode Mock Response ---
    if app.config["STANDALONE_MODE"]:
        job_id = f"mock-{int(time.time())}"
        app.logger.info(f"Standalone mode: Mocking upload success for user '{email}', job_id '{job_id}'")
        return jsonify({"job_id": job_id, "status": "pending"}), 202

    # --- Call API Gateway ---
    api_gateway_url = app.config["API_GATEWAY_URL"]
    upload_endpoint = f"{api_gateway_url}/upload"
    headers = {"Authorization": f"Bearer {jwt_token}"}
    # Pass file stream correctly
    files = {"file": (file.filename, file.stream, file.mimetype)}
    # Send email and format as form data to the gateway
    data = {"email": email, "output_format": output_format}

    app.logger.info(f"Forwarding upload request for user '{email}' to API Gateway: {upload_endpoint}")
    try:
        response = requests.post(upload_endpoint, files=files, data=data, headers=headers)
        app.logger.debug(f"API Gateway response status for upload: {response.status_code}")
        response.raise_for_status()  # Check for HTTP errors (4xx, 5xx)
        response_data = response.json()
        app.logger.info(f"Upload successful via API Gateway for user '{email}', job_id '{response_data.get('job_id')}'.")
        return jsonify(response_data), response.status_code
    except requests.exceptions.RequestException as e:
        # Log details about the request error
        error_message = f"Failed to contact API Gateway upload service: {e}"
        if e.response is not None:
            error_message += f" (Status: {e.response.status_code}, Response: {e.response.text[:200]})" # Log first 200 chars
        app.logger.error(f"API Gateway Upload Error for user '{email}': {error_message}", exc_info=True)

        # Try to parse a specific error from the gateway's response if possible
        try:
            error_details = e.response.json().get("error", str(e))
            error_message_for_user = f"Upload failed: {error_details}"
        except Exception:
            error_message_for_user = "Failed to communicate with the upload service. Please try again later."

        return jsonify({"error": error_message_for_user}), getattr(e.response, 'status_code', 500) # Return gateway status or 500
    except Exception as e:
        app.logger.error(f"Unexpected Upload Error for user '{email}': {e}", exc_info=True)
        return jsonify({"error": "An unexpected server error occurred during upload."}), 500


@app.route("/status/<job_id>")
def status(job_id):
    """Checks the status of a transcoding job."""
    if app.config["STANDALONE_MODE"]:
        # Mock status progression for standalone testing
        mock_status = (
            "completed" if int(time.time()) % 10 > 5 else "pending"
        )  # Flip status
        return jsonify(
            {
                "job_id": job_id,
                "status": mock_status,
                "download_url": "#" if mock_status == "completed" else None,
            }
        ), 200

    jwt_token = session.get("jwt_token")
    if not jwt_token:
        app.logger.warning(f"Status check failed for job '{job_id}': Authentication required.")
        return jsonify({"error": "Authentication required"}), 401

    user_email = session.get("user_info", {}).get('email', 'Unknown User')
    api_gateway_url = app.config["API_GATEWAY_URL"]
    status_endpoint = f"{api_gateway_url}/status/{job_id}"
    headers = {"Authorization": f"Bearer {jwt_token}"}

    app.logger.debug(f"Requesting status for job '{job_id}' (user '{user_email}') from API Gateway: {status_endpoint}")
    try:
        response = requests.get(status_endpoint, headers=headers)
        app.logger.debug(f"API Gateway response status for status check: {response.status_code}")
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        error_message = f"Failed to get job status from API Gateway: {e}"
        if e.response is not None:
            error_message += f" (Status: {e.response.status_code}, Response: {e.response.text[:200]})"
        app.logger.error(f"API Gateway Status Error for job '{job_id}' (user '{user_email}'): {error_message}", exc_info=True)
        return jsonify({"error": "Failed to get job status. Please try again later."}), getattr(e.response, 'status_code', 500)
    except Exception as e:
        app.logger.error(f"Unexpected Status Error for job '{job_id}' (user '{user_email}'): {e}", exc_info=True)
        return jsonify({"error": "An unexpected server error occurred checking status."}), 500


# --- Helper Functions ---


def get_user_jobs():
    """Fetches recent jobs for the logged-in user from the API Gateway."""
    jwt_token = session.get("jwt_token")
    if not jwt_token or app.config["STANDALONE_MODE"]:
        return [] # No jobs if not logged in or in standalone

    user_email = session.get("user_info", {}).get('email', 'Unknown User')
    api_gateway_url = app.config["API_GATEWAY_URL"]
    jobs_endpoint = f"{api_gateway_url}/jobs"
    headers = {"Authorization": f"Bearer {jwt_token}"}

    app.logger.debug(f"Fetching job history for user '{user_email}' from API Gateway: {jobs_endpoint}")
    try:
        response = requests.get(jobs_endpoint, headers=headers)
        app.logger.debug(f"API Gateway response status for jobs fetch: {response.status_code}")
        response.raise_for_status()
        jobs_data = response.json()
        app.logger.info(f"Successfully fetched {len(jobs_data)} jobs for user '{user_email}'.")
        return jobs_data
    except requests.exceptions.RequestException as e:
        error_message = f"Failed to get job history from API Gateway: {e}"
        if e.response is not None:
            error_message += f" (Status: {e.response.status_code}, Response: {e.response.text[:200]})"
        app.logger.error(f"API Gateway Get Jobs Error for user '{user_email}': {error_message}", exc_info=True)
        flash("Could not retrieve job history at this time.", "warning")
        return []
    except Exception as e:
        app.logger.error(f"Unexpected Get Jobs Error for user '{user_email}': {e}", exc_info=True)
        flash("An unexpected error occurred retrieving job history.", "warning")
        return []


def get_mock_jobs():
    """Returns mock job data for standalone mode."""
    # Simple mock data
    return [
        {"job_id": "mock-1", "filename": "presentation.mov", "output_format": "MP4", "status": "completed", "download_url": "#"},
        {"job_id": "mock-2", "filename": "podcast.wav", "output_format": "MP3", "status": "completed", "download_url": "#"},
        {"job_id": "mock-3", "filename": "recording.mkv", "output_format": "MP4", "status": "failed", "download_url": None},
        {"job_id": "mock-4", "filename": "inprogress.avi", "output_format": "WebM", "status": "pending", "download_url": None},
    ]

# --- Logging Setup ---
# Configure logging based on DEBUG mode from config.py
log_level = logging.DEBUG if app.config['DEBUG'] else logging.INFO
logging.basicConfig(level=log_level, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

# --- Main Execution ---
if __name__ == "__main__":
    # Host 0.0.0.0 makes it accessible externally (within Docker network)
    # Port 8000 matches docker-compose
    # debug=app.config['DEBUG'] enables/disables Flask debugger and reloader
    app.logger.info(f"Starting Flask server (Debug: {app.config['DEBUG']})...")
    app.run(host="0.0.0.0", port=8000, debug=app.config["DEBUG"])