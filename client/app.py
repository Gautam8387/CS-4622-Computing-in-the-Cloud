# ./client/app.py
import os
from datetime import datetime  # Needed for timestamp formatting
from functools import wraps
from urllib.parse import urlencode

import jwt  # PyJWT
import requests
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

# --- Configuration (from environment variables) ---
app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "insecure-fallback-key-for-dev"
)  # Use env var in prod!

# OAuth Provider Details
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")

# Service URLs
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:5002")
API_GATEWAY_URL_INTERNAL = os.environ.get(
    "API_GATEWAY_URL_INTERNAL", "http://api-gateway:5001"
)
# JS needs the URL it can access from the browser
API_GATEWAY_URL_FOR_BROWSER = os.environ.get(
    "API_GATEWAY_URL_FOR_BROWSER", "http://localhost:5001"
)
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")


# --- Custom Jinja Filter for Timestamps ---
@app.template_filter("datetimeformat")
def format_datetime(value, format="%Y-%m-%d %H:%M:%S UTC"):
    """Format an integer timestamp into a datetime string."""
    if value is None:  # Allow 0 timestamp
        return "N/A"
    if not isinstance(value, (int, float, str)):
        return "Invalid Type"
    try:
        # Ensure value is treated as seconds since epoch
        timestamp = int(value)
        # Handle potential edge cases like year far out of range
        if (
            timestamp < -62167219200 or timestamp > 253402300799
        ):  # Between year 1 and 9999 roughly
            raise ValueError("Timestamp out of range")
        dt_object = datetime.utcfromtimestamp(timestamp)
        return dt_object.strftime(format)
    except (ValueError, TypeError, OverflowError, OSError):
        app.logger.warning(f"Could not format timestamp: {value}", exc_info=False)
        return "Invalid Date"


# --- Helper Functions ---
def get_user_info_from_jwt(token):
    """Safely decodes JWT to get user info without verifying signature."""
    if not token:
        return None
    try:
        # Signature verification happens at API Gateway
        decoded = jwt.decode(
            token, options={"verify_signature": False}, algorithms=[JWT_ALGORITHM]
        )
        # Ensure email is present, as it's used as an identifier
        if not decoded.get("email"):
            app.logger.warning("JWT decoded but missing 'email' claim.")
            return None
        return {"name": decoded.get("name"), "email": decoded.get("email")}
    except jwt.ExpiredSignatureError:
        app.logger.info("Attempted to use expired JWT.")
        session.pop("jwt", None)  # Clear expired token
        return None
    except jwt.InvalidTokenError as e:
        app.logger.warning(f"Attempted to use invalid JWT: {e}")
        session.pop("jwt", None)  # Clear invalid token
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error decoding JWT: {e}", exc_info=True)
        session.pop("jwt", None)
        return None


# Decorator to check if user is logged in via session JWT
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = session.get("jwt")
        if not token:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("index"))
        # Re-validate token info on protected actions
        user_info = get_user_info_from_jwt(
            token
        )  # This also handles clearing session if invalid
        if not user_info:
            flash(
                "Your session has expired or is invalid. Please log in again.",
                "warning",
            )
            # Redirect to index which will show login buttons
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


# --- Routes ---
@app.route("/")
def index():
    """Renders the main page and fetches job history if logged in for initial display."""
    user_info = None
    job_history = []  # Default to empty list
    jwt_token = session.get("jwt")
    is_logged_in = False  # Flag for JS

    if jwt_token:
        user_info = get_user_info_from_jwt(jwt_token)  # Validate token
        if user_info:
            is_logged_in = True  # User is considered logged in for this request
            # --- Fetch Job History (Initial Load Only) ---
            api_url = f"{API_GATEWAY_URL_INTERNAL}/jobs"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            try:
                app.logger.info(
                    f"Initial history fetch for {user_info.get('email')} from {api_url}"
                )
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx/5xx)

                # Ensure response is valid JSON before parsing
                if "application/json" in response.headers.get("Content-Type", ""):
                    job_history = response.json()  # Expecting a list of job dicts
                    if not isinstance(job_history, list):
                        app.logger.error(
                            f"API Gateway /jobs did not return a list: {job_history}"
                        )
                        job_history = []  # Reset to empty on invalid format
                    else:
                        app.logger.info(
                            f"Initial fetch received {len(job_history)} jobs."
                        )
                else:
                    app.logger.error(
                        f"API Gateway /jobs did not return JSON. Content-Type: {response.headers.get('Content-Type')}"
                    )
                    job_history = []

            except requests.exceptions.HTTPError as e:
                # Handle specific errors (e.g., 401, 403 from gateway)
                status_code = e.response.status_code if e.response else None
                if status_code in [401, 403]:
                    # This might happen if JWT expired between get_user_info and API call
                    app.logger.warning(
                        f"Auth error ({status_code}) during initial history fetch. Clearing session."
                    )
                    session.pop("jwt", None)
                    is_logged_in = False  # Update flag
                    user_info = None
                    flash("Your session expired. Please log in again.", "warning")
                    # Don't redirect here, just render logged-out state
                else:
                    error_msg = (
                        f"Error fetching job history: {status_code or 'Unknown Status'}"
                    )
                    try:  # Try to get detail from gateway response
                        error_details = e.response.json().get("error", e.response.text)
                        error_msg += f" - {error_details}"
                    except Exception:
                        pass  # Ignore if response isn't JSON
                    app.logger.error(
                        f"HTTPError fetching job history: {error_msg}", exc_info=False
                    )
                    flash(error_msg, "danger")  # Show error on initial load

            except requests.exceptions.RequestException as e:
                app.logger.error(f"Network error fetching job history: {e}")
                flash("Could not connect to history service.", "warning")
            except Exception as e:
                app.logger.error(
                    f"Unexpected error fetching job history: {e}", exc_info=True
                )
                flash(
                    "An unexpected error occurred while fetching job history.", "danger"
                )
        # else: user_info is None, user is effectively logged out

    # Pass config needed by JavaScript
    js_config = {
        "api_gateway_url": API_GATEWAY_URL_FOR_BROWSER,
        "is_logged_in": is_logged_in,  # Tell JS if user is logged in for this page load
    }
    # Pass user_info and initial job_history to the template
    return render_template(
        "index.html", user_info=user_info, js_config=js_config, job_history=job_history
    )


# --- Submit Job Route ---
@app.route("/submit_job", methods=["POST"])
@login_required  # Ensures valid JWT exists before processing
def submit_job():
    """Handles the direct form submission for transcoding jobs."""
    token = session.get("jwt")  # Already validated by decorator somewhat
    # Re-fetch user_info in case roles/etc changed, though not strictly needed here
    user_info = get_user_info_from_jwt(token)
    if not user_info:  # Should not happen if @login_required worked, but safety check
        flash("Authentication error. Please log in again.", "danger")
        return redirect(url_for("logout"))

    if "media_file" not in request.files or not request.files["media_file"].filename:
        flash("No file selected for upload.", "warning")
        return redirect(url_for("index"))

    file = request.files["media_file"]
    output_format = request.form.get("output_format")
    email = request.form.get(
        "email", user_info.get("email")
    )  # Default to user's primary email

    if not output_format:
        flash("Please select an output format.", "warning")
        return redirect(url_for("index"))

    app.logger.info(
        f"Submit Job: User='{user_info.get('email')}', File='{file.filename}', Format='{output_format}', Notify='{email}'"
    )

    # --- Forward request to API Gateway ---
    api_url = f"{API_GATEWAY_URL_INTERNAL}/upload"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"output_format": output_format}
    if email:
        payload["email"] = email
    files_to_send = {"media_file": (file.filename, file.stream, file.mimetype)}

    try:
        response = requests.post(
            api_url, headers=headers, data=payload, files=files_to_send, timeout=60
        )
        response.raise_for_status()

        data = response.json()
        job_id = data.get("job_id")
        if job_id:
            flash(
                f"Transcoding job submitted successfully! Job ID: {job_id}. History will update shortly.",
                "success",
            )
        else:
            app.logger.error(
                f"API Gateway accepted upload but did not return job_id. Response: {data}"
            )
            flash(
                "Job submitted, but there was an issue tracking it. Please check history later.",
                "warning",
            )
        return redirect(url_for("index"))

    except requests.exceptions.HTTPError as e:
        error_message = f"Error submitting job: {e.response.status_code}"
        try:
            error_details = e.response.json().get("error", e.response.text)
            error_message += f" - {error_details}"
        except Exception:
            error_message += f" - {e.response.text}"
        app.logger.error(
            f"HTTPError calling API Gateway /upload: {error_message}", exc_info=True
        )
        flash(error_message, "danger")
        return redirect(url_for("index"))
    except requests.exceptions.RequestException as e:
        app.logger.error(
            f"Network error calling API Gateway /upload: {e}", exc_info=True
        )
        flash(f"Could not connect to the processing service: {e}", "danger")
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Unexpected error in submit_job: {e}", exc_info=True)
        flash("An unexpected error occurred while submitting the job.", "danger")
        return redirect(url_for("index"))


# --- OAuth Login Initiation ---
@app.route("/login/google")
def login_google():
    if not GOOGLE_CLIENT_ID:
        flash("Google login is not configured.", "danger")
        return redirect(url_for("index"))
    google_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": url_for("callback_google", _external=True),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return redirect(
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(google_params)}"
    )


@app.route("/login/github")
def login_github():
    if not GITHUB_CLIENT_ID:
        flash("GitHub login is not configured.", "danger")
        return redirect(url_for("index"))
    github_params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": url_for("callback_github", _external=True),
        "scope": "user:email read:user",
        "state": "random_csrf",
    }  # TODO: Implement CSRF state token
    return redirect(
        f"https://github.com/login/oauth/authorize?{urlencode(github_params)}"
    )


# --- OAuth Callback Handling ---
@app.route("/callback/google")
def callback_google():
    code = request.args.get("code")
    if not code:
        flash("Login failed: No authorization code received from Google.", "danger")
        return redirect(url_for("index"))
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/token",
            json={
                "provider": "google",
                "code": code,
                "redirect_uri": url_for("callback_google", _external=True),
            },
        )
        response.raise_for_status()
        data = response.json()
        jwt_token = data.get("access_token")
        if jwt_token:
            session["jwt"] = jwt_token
            flash("Successfully logged in with Google!", "success")
            return redirect(url_for("index"))
        else:
            flash(f"Login failed: {data.get('error', 'Unknown auth error')}", "danger")
            return redirect(url_for("index"))
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error contacting auth service for Google token: {e}")
        flash("Login failed: Cannot connect to auth service.", "danger")
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Generic error during Google callback: {e}")
        flash("An unexpected error occurred during login.", "danger")
        return redirect(url_for("index"))


@app.route("/callback/github")
def callback_github():
    code = request.args.get("code")
    _ = request.args.get("state")  # TODO: Verify state
    if not code:
        flash("Login failed: No authorization code received from GitHub.", "danger")
        return redirect(url_for("index"))
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/token",
            json={
                "provider": "github",
                "code": code,
                "redirect_uri": url_for("callback_github", _external=True),
            },
        )
        response.raise_for_status()
        data = response.json()
        jwt_token = data.get("access_token")
        if jwt_token:
            session["jwt"] = jwt_token
            flash("Successfully logged in with GitHub!", "success")
            return redirect(url_for("index"))
        else:
            flash(f"Login failed: {data.get('error', 'Unknown auth error')}", "danger")
            return redirect(url_for("index"))
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error contacting auth service for GitHub token: {e}")
        flash("Login failed: Cannot connect to auth service.", "danger")
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Generic error during GitHub callback: {e}")
        flash("An unexpected error occurred during login.", "danger")
        return redirect(url_for("index"))


# --- Logout ---
@app.route("/logout")
def logout():
    session.pop("jwt", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# --- API for JavaScript (Token needed for periodic refresh) ---
@app.route("/get-token")
def get_token():
    """Securely provides the JWT stored in the session to the frontend JS."""
    token = session.get("jwt")
    if token:
        user_info = get_user_info_from_jwt(token)  # Re-check validity before sending
        if user_info:
            return jsonify({"access_token": token})
        else:
            return jsonify(
                {"error": "Invalid session token"}
            ), 401  # Tell JS session is bad
    else:
        return jsonify({"error": "Not authenticated"}), 401


if __name__ == "__main__":
    app.run(
        host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_ENV") == "development"
    )
