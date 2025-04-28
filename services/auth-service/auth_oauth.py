# ./services/auth-service/auth_oauth.py
from datetime import datetime, timedelta

import jwt  # For creating JWTs
import requests
from authlib.integrations.flask_client import OAuth
from common import setup_logger

# Load environment variables
from dotenv import load_dotenv
from flask import (  # Removed url_for as logins are initiated by client
    Flask,
    jsonify,
    request,
)

load_dotenv()

app = Flask(__name__)
app.config.from_pyfile("config.py")  # Load config from config.py
logger = setup_logger()

oauth = OAuth(app)

# Google Config (fetches metadata automatically)
google = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# GitHub Config
github = oauth.register(
    name="github",
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email read:user"},  # request email scope
)


@app.route("/auth/token", methods=["POST"])
def exchange_token():
    """
    Exchanges an OAuth provider token (received by the client) for a local JWT.
    Expects JSON payload: {'provider': 'google'|'github', 'token': <provider_token_object>}
    """
    data = request.get_json()
    if not data or "provider" not in data or "token" not in data:
        return jsonify({"error": "Invalid request payload"}), 400

    provider_name = data["provider"]
    provider_token = data["token"]  # The token object received by the client's callback

    if provider_name not in oauth.clients:
        return jsonify({"error": f"Unsupported provider: {provider_name}"}), 400

    # Use the provider's client to fetch user info using the provided token
    oauth_provider = getattr(oauth, provider_name)
    try:
        # Authlib uses the 'token' object directly for requests
        if provider_name == "google":
            # Google uses OIDC userinfo endpoint
            userinfo_endpoint = oauth_provider.server_metadata.get("userinfo_endpoint")
            if not userinfo_endpoint:
                raise Exception("Could not find userinfo endpoint for Google")
            resp = oauth_provider.get(userinfo_endpoint, token=provider_token)
            resp.raise_for_status()
            user_info = resp.json()
            email = user_info.get("email")
            name = user_info.get("name")
            if not email:  # Should typically always be present with 'email' scope
                raise Exception("Email not found in Google user info")

        elif provider_name == "github":
            # GitHub requires separate calls for user profile and email
            resp_user = oauth_provider.get("user", token=provider_token)
            resp_user.raise_for_status()
            user_profile = resp_user.json()

            # Fetch emails
            resp_emails = oauth_provider.get("user/emails", token=provider_token)
            resp_emails.raise_for_status()
            emails = resp_emails.json()

            email = None
            primary_email = next((e["email"] for e in emails if e.get("primary")), None)
            if primary_email:
                email = primary_email
            elif emails:  # Fallback to first email if no primary
                email = emails[0]["email"]

            if (
                not email
            ):  # Use login as fallback identifier if email is missing/private
                email = user_profile.get("login") + "@github.user"  # Placeholder email

            name = user_profile.get("name") or user_profile.get(
                "login"
            )  # Use login if name is missing

        else:
            raise Exception(f"User info fetching not implemented for {provider_name}")

        # --- Generate JWT Token ---
        jwt_payload = {
            "sub": email,  # Subject (standard claim)
            "email": email,
            "name": name,
            "provider": provider_name,
            "iat": datetime.utcnow(),  # Issued at time
            "exp": datetime.utcnow()
            + timedelta(hours=1),  # Expiration time (e.g., 1 hour)
        }
        jwt_secret = app.config["SECRET_KEY"]
        jwt_token = jwt.encode(jwt_payload, jwt_secret, algorithm="HS256")

        logger.info(f"JWT issued for user {email} via {provider_name}")

        # Return JWT and user info to the client
        return jsonify(
            {
                "token": jwt_token,
                "user": {  # Return consistent user object shape
                    "email": email,
                    "name": name,
                    "provider": provider_name,
                },
            }
        ), 200

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to fetch user info from {provider_name}: {e}", exc_info=True
        )
        status_code = e.response.status_code if e.response is not None else 500
        error_detail = str(e)
        try:  # Try to get more specific error from provider response
            error_detail = e.response.json()
        except Exception as e:
            print(f"Failed to parse error response: {e}")  # Log parsing error but continue
            pass
        return jsonify(
            {
                "error": f"Failed to validate token with {provider_name}",
                "details": error_detail,
            }
        ), status_code
    except Exception as e:
        logger.error(
            f"Error during token exchange for {provider_name}: {e}", exc_info=True
        )
        return jsonify(
            {"error": f"Internal server error during token exchange: {e}"}
        ), 500


# NOTE: Add a logout endpoint for JWT blocklisting for future use
# @app.route("/auth/logout", methods=["POST"])
# def logout():
#     # Requires storing revoked tokens (e.g., in Redis) until they expire
#     # token = request.headers.get("Authorization", "").split(" ")[-1]
#     # if token:
#     #     # Add token JTI (JWT ID) or signature to blocklist in Redis with TTL = remaining validity
#     #     pass
#     return jsonify({"message": "Logout endpoint placeholder"}), 200

if __name__ == "__main__":
    # Auth service runs on port 5001
    app.run(host="0.0.0.0", port=5001, debug=app.config["DEBUG"])
