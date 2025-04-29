# ./services/auth-service/app.py
import logging
import os
import time

import jwt  # PyJWT
import requests
# from dotenv import dotenv_values
from flask import Flask, jsonify, request

# --- Configuration ---
# Load .env file from project root
config = {
    # **dotenv_values(".env"),  # load development variables
    **os.environ,  # override loaded values with environment variables
}

app = Flask(__name__)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OAuth Provider Details (Load from .env)
GOOGLE_CLIENT_ID = config.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = config.get("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = config.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = config.get("GITHUB_CLIENT_SECRET")

# JWT Configuration
JWT_SECRET_KEY = config.get("JWT_SECRET_KEY", "default-fallback-secret-key-change-me")
JWT_ALGORITHM = config.get("JWT_ALGORITHM", "HS256")
try:
    JWT_EXPIRATION_SECONDS = int(
        config.get("JWT_EXPIRATION_SECONDS", 86400)
    )  # Default 24 hours
except ValueError:
    JWT_EXPIRATION_SECONDS = 86400
    logger.warning(
        f"Invalid JWT_EXPIRATION_SECONDS, defaulting to {JWT_EXPIRATION_SECONDS}"
    )


# OAuth Endpoint URLs
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = (
    "https://www.googleapis.com/oauth2/v3/userinfo"  # Or openid endpoint
)
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERAPI_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = (
    "https://api.github.com/user/emails"  # Need separate call for primary email
)

# --- Helper Functions ---


def exchange_google_code_for_token(code, redirect_uri):
    """Exchanges Google authorization code for access token."""
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    headers = {"Accept": "application/json"}
    try:
        response = requests.post(
            GOOGLE_TOKEN_URL, data=payload, headers=headers, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error exchanging Google code: {e} - Response: {e.response.text if e.response else 'No response'}"
        )
        raise ValueError(f"Failed to exchange Google code: {e}") from e


def get_google_user_info(access_token):
    """Fetches user info from Google using access token."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=10)
        response.raise_for_status()
        user_info = response.json()
        # Ensure essential fields are present
        if not user_info.get("email") or not user_info.get("sub"):
            raise ValueError("Google user info missing required fields (email or sub)")
        return {
            "email": user_info.get("email"),
            "name": user_info.get(
                "name", user_info.get("given_name")
            ),  # Prefer 'name', fallback to 'given_name'
            "provider_id": user_info.get("sub"),  # Google's unique ID
        }
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error fetching Google user info: {e} - Response: {e.response.text if e.response else 'No response'}"
        )
        raise ValueError(f"Failed to fetch Google user info: {e}") from e


def exchange_github_code_for_token(code):
    """Exchanges GitHub authorization code for access token."""
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        # 'redirect_uri': redirect_uri # Optional but good practice if set in GitHub app
    }
    headers = {
        "Accept": "application/json"  # Request JSON response
    }
    try:
        response = requests.post(
            GITHUB_TOKEN_URL, data=payload, headers=headers, timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(
                f"GitHub token exchange error: {data.get('error_description', data['error'])}"
            )
        if "access_token" not in data:
            raise ValueError("GitHub response missing access_token")
        return data["access_token"]
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error exchanging GitHub code: {e} - Response: {e.response.text if e.response else 'No response'}"
        )
        raise ValueError(f"Failed to exchange GitHub code: {e}") from e


def get_github_user_info(access_token):
    """Fetches user info from GitHub using access token."""
    headers = {
        "Authorization": f"token {access_token}",  # Note the 'token' prefix
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        # Get basic user profile
        user_response = requests.get(GITHUB_USERAPI_URL, headers=headers, timeout=10)
        user_response.raise_for_status()
        user_data = user_response.json()

        # Get user emails to find the primary one
        emails_response = requests.get(
            GITHUB_USER_EMAILS_URL, headers=headers, timeout=10
        )
        emails_response.raise_for_status()
        emails_data = emails_response.json()

        primary_email = None
        for email_info in emails_data:
            if email_info.get("primary") and email_info.get("verified"):
                primary_email = email_info.get("email")
                break
        # Fallback if no primary email found (should be rare for verified accounts)
        if not primary_email and emails_data:
            verified_emails = [e["email"] for e in emails_data if e.get("verified")]
            if verified_emails:
                primary_email = verified_emails[0]  # Pick the first verified one

        if not primary_email:
            # If still no email, try the public email field from the user profile (might be null)
            primary_email = user_data.get("email")

        if not primary_email:
            raise ValueError("Could not retrieve a verified primary email from GitHub.")
        if not user_data.get("id"):
            raise ValueError("GitHub user info missing required field (id)")

        return {
            "email": primary_email,
            "name": user_data.get(
                "name", user_data.get("login")
            ),  # Prefer 'name', fallback to 'login' username
            "provider_id": user_data.get("id"),  # GitHub's unique ID
        }
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error fetching GitHub user info: {e} - Response: {e.response.text if e.response else 'No response'}"
        )
        raise ValueError(f"Failed to fetch GitHub user info: {e}") from e


def create_jwt(user_info):
    """Creates a JWT for the given user info."""
    payload = {
        "email": user_info["email"],
        "name": user_info.get("name"),
        "provider_id": user_info.get("provider_id"),
        "provider": user_info.get("provider"),  # Add which provider was used
        "iat": int(time.time()),  # Issued at time
        "exp": int(time.time()) + JWT_EXPIRATION_SECONDS,  # Expiration time
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


# --- Routes ---


@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    # Check if essential config is present
    if not JWT_SECRET_KEY or JWT_SECRET_KEY == "default-fallback-secret-key-change-me":
        logger.error("JWT_SECRET_KEY is not set or is using default value.")
        return jsonify(
            {"status": "unhealthy", "reason": "JWT_SECRET_KEY not configured"}
        ), 500
    # Could add checks for provider configs if needed
    return jsonify({"status": "healthy"}), 200


@app.route("/auth/token", methods=["POST"])
def get_token():
    """
    Exchanges provider authorization code for our application's JWT.
    Expects JSON payload: {"provider": "google|github", "code": "...", "redirect_uri": "..." (optional)}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    provider = data.get("provider")
    code = data.get("code")
    redirect_uri = data.get("redirect_uri")  # Required for Google, optional for GitHub

    if not provider or provider not in ["google", "github"]:
        return jsonify({"error": "Missing or invalid provider specified"}), 400
    if not code:
        return jsonify({"error": "Missing authorization code"}), 400

    logger.info(f"Received token exchange request for provider: {provider}")

    try:
        user_info = None
        if provider == "google":
            if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
                logger.error("Google OAuth is not configured on the server.")
                return jsonify({"error": "Google Sign-In is not configured"}), 500
            if not redirect_uri:
                return jsonify({"error": "Missing redirect_uri for Google"}), 400

            token_data = exchange_google_code_for_token(code, redirect_uri)
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError("Did not receive access_token from Google")
            user_info = get_google_user_info(access_token)

        elif provider == "github":
            if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
                logger.error("GitHub OAuth is not configured on the server.")
                return jsonify({"error": "GitHub Sign-In is not configured"}), 500

            access_token = exchange_github_code_for_token(code)
            user_info = get_github_user_info(access_token)

        if user_info:
            user_info["provider"] = provider  # Add provider info before creating JWT
            # --- Optional: User Persistence/Lookup ---
            # Here you could potentially:
            # 1. Look up the user in your own database by provider_id/email.
            # 2. Create a new user record if they don't exist.
            # 3. Add internal user ID or roles to the JWT payload.
            # For this project scope, we'll just use the info directly.
            # --- End Optional ---

            # Create our application-specific JWT
            app_jwt = create_jwt(user_info)
            logger.info(
                f"Successfully generated JWT for user: {user_info.get('email')} via {provider}"
            )
            return jsonify({"access_token": app_jwt, "token_type": "bearer"})

        else:
            # Should not happen if no exception was raised, but as a safeguard
            logger.error(
                f"User info retrieval failed unexpectedly for provider {provider}."
            )
            return jsonify(
                {"error": "Failed to retrieve user information after token exchange"}
            ), 500

    except ValueError as e:
        # Catch specific value errors from our helpers (e.g., bad response, missing fields)
        logger.error(f"Value error during token exchange for {provider}: {e}")
        return jsonify({"error": str(e)}), 400  # Bad Request might be appropriate
    except Exception as e:
        # Catch unexpected errors (requests exceptions, JWT errors, etc.)
        logger.exception(
            f"Unexpected error during token exchange for {provider}: {e}"
        )  # Log traceback
        return jsonify({"error": f"An internal server error occurred: {e}"}), 500


if __name__ == "__main__":
    # Use 0.0.0.0 to be accessible within Docker network
    # Port 5002 as per docker-compose example
    app.run(host="0.0.0.0", port=5002, debug=config.get("FLASK_ENV") == "development")
