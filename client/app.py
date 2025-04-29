# ./client/app.py
import os
from urllib.parse import urlencode

import jwt  # PyJWT
import requests
# from dotenv import dotenv_values
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

# --- Configuration ---
# Load environment variables from .env file located at the project root
# config = dotenv_values(".env")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "default-fallback-secret-key-change-me"
)  # IMPORTANT: Load from env var in production

# OAuth Provider Details (Load from .env)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get(
    "GOOGLE_CLIENT_SECRET"
)  # Although secret used by auth-service, ID is needed here
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get(
    "GITHUB_CLIENT_SECRET"
)  # Although secret used by auth-service, ID is needed here

# Service URLs (Assume running via docker-compose, use service names)
# In a real deployment, these might come from env vars or service discovery
AUTH_SERVICE_URL = os.environ.get(
    "AUTH_SERVICE_URL", "http://auth-service:5002"
)  # Internal URL for server-to-server
API_GATEWAY_URL_FOR_BROWSER = os.environ.get(
    "API_GATEWAY_URL_FOR_BROWSER", "http://localhost:5001"
)  # URL browser uses


# --- Helper Functions ---
def get_user_info_from_jwt(token):
    """Safely decodes JWT to get user info without verifying signature (verification happens at gateway)."""
    if not token:
        return None
    try:
        # Decode without verification is okay here as we only use it for display
        # The API Gateway is responsible for actual verification
        decoded = jwt.decode(
            token, options={"verify_signature": False}, algorithms=["HS256"]
        )
        return {"name": decoded.get("name"), "email": decoded.get("email")}
    except jwt.ExpiredSignatureError:
        flash("Session expired. Please log in again.", "warning")
        session.pop("jwt", None)  # Clear expired token
        return None
    except jwt.InvalidTokenError:
        flash("Invalid session token. Please log in again.", "danger")
        session.pop("jwt", None)  # Clear invalid token
        return None


# --- Routes ---
@app.route("/")
def index():
    """Renders the main page."""
    user_info = None
    jwt_token = session.get("jwt")
    if jwt_token:
        user_info = get_user_info_from_jwt(jwt_token)
        if not user_info:  # Token was invalid or expired
            return redirect(url_for("logout"))

    # Pass config needed by JavaScript to the template
    js_config = {
        "api_gateway_url": API_GATEWAY_URL_FOR_BROWSER,
        "google_client_id": GOOGLE_CLIENT_ID,  # Needed if using Google JS library directly (not used in this example)
        "github_client_id": GITHUB_CLIENT_ID,  # Needed if constructing GitHub URL in JS (not used here)
    }
    return render_template("index.html", user_info=user_info, js_config=js_config)


# --- OAuth Login Initiation ---
@app.route("/login/google")
def login_google():
    """Redirects user to Google for authentication."""
    if not GOOGLE_CLIENT_ID:
        flash("Google login is not configured.", "danger")
        return redirect(url_for("index"))

    google_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": url_for(
            "callback_google", _external=True
        ),  # Must match Google Console config
        "response_type": "code",
        "scope": "openid email profile",  # Request basic profile info
        "access_type": "offline",  # Optional: if you need refresh tokens
        "prompt": "select_account",
    }
    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    return redirect(f"{google_auth_url}?{urlencode(google_params)}")


@app.route("/login/github")
def login_github():
    """Redirects user to GitHub for authentication."""
    if not GITHUB_CLIENT_ID:
        flash("GitHub login is not configured.", "danger")
        return redirect(url_for("index"))

    github_params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": url_for(
            "callback_github", _external=True
        ),  # Must match GitHub app config
        "scope": "user:email read:user",  # Request email and basic profile
        "state": "random_string_for_csrf_prevention",  # TODO: Implement proper CSRF state token
    }
    github_auth_url = "https://github.com/login/oauth/authorize"
    return redirect(f"{github_auth_url}?{urlencode(github_params)}")


# --- OAuth Callback Handling ---
@app.route("/callback/google")
def callback_google():
    """Handles the callback from Google after user authentication."""
    code = request.args.get("code")
    if not code:
        flash("Login failed: No authorization code received from Google.", "danger")
        return redirect(url_for("index"))

    # Exchange the code for a JWT from our auth-service
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/token",
            json={
                "provider": "google",
                "code": code,
                "redirect_uri": url_for(
                    "callback_google", _external=True
                ),  # Send redirect_uri for verification
            },
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        data = response.json()
        jwt_token = data.get("access_token")

        if jwt_token:
            session["jwt"] = jwt_token  # Store JWT in secure session cookie
            flash("Successfully logged in with Google!", "success")
            return redirect(url_for("index"))
        else:
            flash(
                f"Login failed: {data.get('error', 'Could not retrieve token from auth service.')}",
                "danger",
            )
            return redirect(url_for("index"))

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error contacting auth service for Google token: {e}")
        flash(
            f"Login failed: Could not connect to authentication service ({e}).",
            "danger",
        )
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Generic error during Google callback: {e}")
        flash("An unexpected error occurred during login.", "danger")
        return redirect(url_for("index"))


@app.route("/callback/github")
def callback_github():
    """Handles the callback from GitHub after user authentication."""
    code = request.args.get("code")
    _ = request.args.get("state")  # TODO: Verify state matches the one sent

    if not code:
        flash("Login failed: No authorization code received from GitHub.", "danger")
        return redirect(url_for("index"))

    # Exchange the code for a JWT from our auth-service
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/token",
            json={
                "provider": "github",
                "code": code,
                "redirect_uri": url_for(
                    "callback_github", _external=True
                ),  # Not always required by GitHub server-side, but good practice
            },
        )
        response.raise_for_status()

        data = response.json()
        jwt_token = data.get("access_token")

        if jwt_token:
            session["jwt"] = jwt_token  # Store JWT in secure session cookie
            flash("Successfully logged in with GitHub!", "success")
            return redirect(url_for("index"))
        else:
            flash(
                f"Login failed: {data.get('error', 'Could not retrieve token from auth service.')}",
                "danger",
            )
            return redirect(url_for("index"))

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error contacting auth service for GitHub token: {e}")
        flash(
            f"Login failed: Could not connect to authentication service ({e}).",
            "danger",
        )
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Generic error during GitHub callback: {e}")
        flash("An unexpected error occurred during login.", "danger")
        return redirect(url_for("index"))


# --- Logout ---
@app.route("/logout")
def logout():
    """Clears the session JWT."""
    session.pop("jwt", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# --- API for JavaScript ---
@app.route("/get-token")
def get_token():
    """Securely provides the JWT stored in the session to the frontend JS."""
    token = session.get("jwt")
    if token:
        # Optional: Add check here if token is close to expiry and refresh if needed
        # This would require coordination with the auth-service (refresh token flow)
        return jsonify({"access_token": token})
    else:
        return jsonify({"error": "Not authenticated"}), 401


if __name__ == "__main__":
    # Use 0.0.0.0 to be accessible within Docker network
    app.run(
        host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_ENV") == "development"
    )
