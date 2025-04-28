# ./client/app.py
import time
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
    if provider not in oauth.clients:
        flash(f"Unknown OAuth provider: {provider}", "error")
        return redirect(url_for("index"))

    # Make sure callback URL is correctly configured
    redirect_uri = app.config.get("OAUTH_CALLBACK_URL")
    if not redirect_uri:
        flash("OAuth callback URL not configured.", "error")
        return redirect(url_for("index"))

    # Generate a state parameter for CSRF protection
    # state = secrets.token_urlsafe(16)
    # session['oauth_state'] = state
    # print(f"Generated state: {state}") # Debug

    # Use the registered provider object (google or github)
    oauth_provider = getattr(oauth, provider)
    # return oauth_provider.authorize_redirect(redirect_uri, state=state) # Add state if using it
    return oauth_provider.authorize_redirect(redirect_uri)


@app.route("/callback")
def callback():
    """Handles the callback from the OAuth provider."""
    # Determine provider from URL or state (if implemented)
    provider_name = "google" if "google" in request.url else "github"
    oauth_provider = getattr(oauth, provider_name)

    try:
        # Authorize access token
        token = oauth_provider.authorize_access_token()
        # print(f"Received provider token: {token}") # Debug

        # --- Exchange provider token for our JWT ---
        auth_service_url = app.config["AUTH_SERVICE_URL"]
        exchange_url = f"{auth_service_url}/auth/token"
        payload = {
            "provider": provider_name,
            "token": token,  # Send the whole token object
        }
        response = requests.post(exchange_url, json=payload)
        response.raise_for_status()  # Raise exception for bad status codes

        jwt_data = response.json()
        # print(f"Received JWT data: {jwt_data}") # Debug

        # Store JWT and user info in session
        session["jwt_token"] = jwt_data["token"]
        session["user_info"] = jwt_data["user"]  # Auth service provides user info
        flash("Login successful!", "success")

    except Exception as e:
        print(f"OAuth Callback Error: {e}")  # Log the error
        flash(f"Authentication failed: {e}", "error")

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    """Logs the user out by clearing the session."""
    # Optional: Call auth service to invalidate JWT if blocklisting is implemented
    session.pop("jwt_token", None)
    session.pop("user_info", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles file upload requests."""
    # --- Authentication Check ---
    jwt_token = session.get("jwt_token")
    if not jwt_token and not app.config["STANDALONE_MODE"]:
        return jsonify({"error": "Authentication required"}), 401

    # --- File and Form Data Validation ---
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    email = request.form.get("email")  # Email might come from JWT instead
    output_format = request.form.get("output_format")

    # Get user email from session if available
    user_info = session.get("user_info")
    if user_info and "email" in user_info:
        email = user_info["email"]

    if not file or file.filename == "" or not email or not output_format:
        return jsonify({"error": "File, email, and output format are required"}), 400

    # --- File Type Validation ---
    mime_type, _ = guess_type(file.filename)
    file_type = "unknown"
    if mime_type:
        if mime_type.startswith("video/"):
            file_type = "video"
        elif mime_type.startswith("audio/"):
            file_type = "audio"

    if file_type == "unknown":
        return jsonify({"error": "Unsupported file type."}), 400

    # --- Format Validation ---
    valid_formats = app.config["VIDEO_FORMATS"].union(app.config["AUDIO_FORMATS"])
    if file_type == "video" and output_format not in valid_formats:
        return jsonify(
            {"error": f"Invalid output format '{output_format}' for video"}
        ), 400
    if file_type == "audio" and output_format not in app.config["AUDIO_FORMATS"]:
        return jsonify(
            {"error": f"Invalid output format '{output_format}' for audio"}
        ), 400

    # --- Standalone Mode Mock Response ---
    if app.config["STANDALONE_MODE"]:
        job_id = f"mock-{int(time.time())}"
        # Simulate saving job locally if needed for standalone UI
        # save_mock_job(file.filename, output_format, "pending")
        return jsonify({"job_id": job_id, "status": "pending"}), 202  # Simulate pending

    # --- Call API Gateway ---
    api_gateway_url = app.config["API_GATEWAY_URL"]
    headers = {"Authorization": f"Bearer {jwt_token}"}
    files = {"file": (file.filename, file.stream, file.content_type)}
    # Send email and format as form data
    data = {"email": email, "output_format": output_format}

    try:
        response = requests.post(
            f"{api_gateway_url}/upload", files=files, data=data, headers=headers
        )
        response.raise_for_status()  # Check for HTTP errors
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"API Gateway Upload Error: {e}")  # Log error
        error_message = f"Failed to contact upload service: {e}"
        # Try to parse error from response if available
        try:
            error_details = e.response.json().get("error", str(e))
            error_message = f"Upload failed: {error_details}"
        except Exception as e:
            print(f"Error parsing response: {e}")  # Log error
            pass
        return jsonify({"error": error_message}), 500
    except Exception as e:
        print(f"Unexpected Upload Error: {e}")  # Log error
        return jsonify({"error": "An unexpected error occurred during upload."}), 500


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
        return jsonify({"error": "Authentication required"}), 401

    api_gateway_url = app.config["API_GATEWAY_URL"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    try:
        response = requests.get(f"{api_gateway_url}/status/{job_id}", headers=headers)
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"API Gateway Status Error: {e}")  # Log error
        return jsonify({"error": f"Failed to get job status: {e}"}), 500
    except Exception as e:
        print(f"Unexpected Status Error: {e}")  # Log error
        return jsonify({"error": "An unexpected error occurred checking status."}), 500


# --- Helper Functions ---


def get_user_jobs():
    """Fetches recent jobs for the logged-in user from the API Gateway."""
    jwt_token = session.get("jwt_token")
    if not jwt_token or app.config["STANDALONE_MODE"]:
        return []

    api_gateway_url = app.config["API_GATEWAY_URL"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    try:
        response = requests.get(f"{api_gateway_url}/jobs", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Gateway Get Jobs Error: {e}")
        flash("Could not retrieve job history.", "warning")
        return []
    except Exception as e:
        print(f"Unexpected Get Jobs Error: {e}")
        flash("An error occurred retrieving job history.", "warning")
        return []


def get_mock_jobs():
    """Returns mock job data for standalone mode."""
    return [
        {
            "job_id": "mock-1",
            "filename": "presentation.mov",
            "input_format": "MOV",
            "output_format": "MP4",
            "status": "completed",
            "timestamp": "2024-03-10 14:30",
            "download_url": "#",
        },
        {
            "job_id": "mock-2",
            "filename": "podcast.wav",
            "input_format": "WAV",
            "output_format": "MP3",
            "status": "completed",
            "timestamp": "2024-03-10 14:15",
            "download_url": "#",
        },
        {
            "job_id": "mock-3",
            "filename": "recording.mkv",
            "input_format": "MKV",
            "output_format": "MP4",
            "status": "failed",
            "timestamp": "2024-03-10 14:00",
            "download_url": None,
        },
        {
            "job_id": "mock-4",
            "filename": "inprogress.avi",
            "input_format": "AVI",
            "output_format": "MP4",
            "status": "pending",
            "timestamp": "2024-03-10 15:00",
            "download_url": None,
        },
    ]


# --- Main Execution ---
if __name__ == "__main__":
    # Use port 8000 as defined in docker-compose
    app.run(host="0.0.0.0", port=8000, debug=app.config["DEBUG"])

# Running on http://172.28.142.209:8000/