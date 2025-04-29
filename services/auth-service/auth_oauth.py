# ./services/auth-service/auth_oauth.py

import os
import datetime
import jwt  # PyJWT library for generating JWTs
import requests # For GitHub API calls
import logging

from flask import Flask, request, jsonify, current_app
from authlib.integrations.flask_client import OAuth
# Import necessary components from common, assuming they setup logging/connections
# Note: Even if auth-service doesn't *use* all common features, importing __init__
# might trigger imports within common that need libraries like celery, redis, boto3.
from common import setup_logger # Assuming setup_logger configures logging

# --- Constants ---
JWT_ALGORITHM = "HS256"
JWT_EXP_DELTA_HOURS = 8 # How long the JWT is valid

# --- Flask App Setup ---
app = Flask(__name__)

# --- Configuration Loading ---
# Load configuration directly from environment variables
app.config['SECRET_KEY'] = os.environ.get('AUTH_SERVICE_SECRET_KEY') # Use specific key name
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')
app.config['GITHUB_CLIENT_ID'] = os.environ.get('GITHUB_CLIENT_ID')
app.config['GITHUB_CLIENT_SECRET'] = os.environ.get('GITHUB_CLIENT_SECRET')
app.config['DEBUG'] = os.environ.get('FLASK_ENV', 'production').lower() == 'development'

# --- Logging Setup ---
# Use the logger from common or configure a basic one
log_level = logging.DEBUG if app.config['DEBUG'] else logging.INFO
# Assuming setup_logger exists and works, otherwise use basicConfig:
# logging.basicConfig(level=log_level, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
# logger = logging.getLogger(__name__) # Use module-specific logger if basicConfig is used
# If setup_logger handles everything:
try:
    setup_logger() # Configure global logging settings
    logger = logging.getLogger('auth_service') # Get a specific logger for this service
    logger.setLevel(log_level) # Optionally set level specifically for this logger
    logger.info("Logging configured via common.setup_logger.")
except Exception as e:
    # Fallback if setup_logger fails or has issues
    logging.basicConfig(level=log_level, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    logger = logging.getLogger('auth_service')
    logger.error(f"Failed to configure logging via common.setup_logger: {e}. Using basicConfig.", exc_info=True)

# --- Validate Configuration ---
if not app.config['SECRET_KEY']:
    logger.critical("FATAL ERROR: AUTH_SERVICE_SECRET_KEY environment variable is not set.")
    # Optionally raise an exception to prevent startup
    # raise ValueError("AUTH_SERVICE_SECRET_KEY environment variable must be set.")
if not app.config['GOOGLE_CLIENT_ID'] or not app.config['GOOGLE_CLIENT_SECRET']:
    logger.warning("Google OAuth credentials not fully configured. Google login via this service might fail.")
if not app.config['GITHUB_CLIENT_ID'] or not app.config['GITHUB_CLIENT_SECRET']:
    logger.warning("GitHub OAuth credentials not fully configured. GitHub login via this service might fail.")


# --- OAuth Setup (Required for parsing/verification) ---
oauth = OAuth(app)

# Google Registration (needed for parse_id_token)
oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'} # Scope here doesn't initiate login, just for config
)

# GitHub Registration (needed if using Authlib for API calls, less common here)
# Often we use 'requests' directly for GitHub token verification via API
oauth.register(
    name='github',
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize', # Not used here
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email read:user'} # Not used directly here
)

# --- Routes ---

@app.route('/auth/token', methods=['POST'])
def exchange_token():
    """
    Exchanges a provider token (from client app) for a local application JWT.
    Optionally verifies the provider token.
    """
    data = request.get_json()

    # Validate incoming request payload
    if not data or 'provider' not in data or 'token' not in data:
        logger.error("Token exchange request missing provider or token.")
        return jsonify({"error": "Missing provider or token in request"}), 400
    if data['provider'] == 'google' and 'nonce' not in data:
         logger.error("Token exchange request for Google missing nonce.")
         return jsonify({"error": "Missing nonce in request for Google"}), 400

    provider_name = data['provider']
    provider_token_data = data['token'] # This is the token object from client
    received_nonce = data.get('nonce') # Use .get() as it might be None for GitHub

    logger.info(f"Received token exchange request for provider: {provider_name}")

    try:
        # Get the Authlib provider object configured in *this* service
        # This is primarily needed for Google's parse_id_token
        oauth_provider = getattr(oauth, provider_name)
    except AttributeError:
        logger.error(f"Invalid provider name received for token exchange: {provider_name}")
        return jsonify({"error": f"Unsupported provider: {provider_name}"}), 400

    try:
        user_info = None # Initialize

        # --- Process Google Token ---
        if provider_name == 'google':
            if not received_nonce:
                 logger.warning("Nonce missing in request for Google token exchange (should have been caught earlier).")
                 raise ValueError("Nonce is required for Google login verification.")

            logger.debug("Attempting to parse Google ID token.")
            # parse_id_token verifies signature, expiration, nonce, etc.
            user_info_from_id_token = oauth_provider.parse_id_token(provider_token_data, nonce=received_nonce)

            # Optional but recommended: Validate audience claim
            google_client_id = app.config.get('GOOGLE_CLIENT_ID')
            if google_client_id and user_info_from_id_token.get('aud') != google_client_id:
               logger.error(f"Invalid audience ('aud') claim in Google id_token: {user_info_from_id_token.get('aud')}")
               raise ValueError("Invalid audience claim in id_token.")

            # Construct a standardized user_info dictionary
            user_info = {
                'email': user_info_from_id_token.get('email'),
                'name': user_info_from_id_token.get('name'),
                'sub': user_info_from_id_token.get('sub'), # Google subject ID
                'picture': user_info_from_id_token.get('picture')
            }
            logger.debug("Google id_token successfully parsed and validated.")

        # --- Process GitHub Token ---
        elif provider_name == 'github':
            access_token = provider_token_data.get('access_token')
            if not access_token:
                logger.error("Missing access_token in token data received from client for GitHub.")
                raise ValueError("Missing access_token for GitHub")

            logger.debug("Verifying GitHub token by fetching user info.")
            # Verify token by fetching user info from GitHub API
            user_api_url = "https://api.github.com/user"
            headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/vnd.github.v3+json'}
            logger.debug(f"Calling GitHub API: {user_api_url}")
            resp = requests.get(user_api_url, headers=headers)
            resp.raise_for_status() # Raise HTTPError for 4xx/5xx responses
            github_user = resp.json()
            github_login = github_user.get('login')
            logger.debug(f"GitHub user data received for login: {github_login}")

            # Fetch emails to get the primary verified one
            email_api_url = "https://api.github.com/user/emails"
            logger.debug(f"Calling GitHub Emails API: {email_api_url}")
            email_resp = requests.get(email_api_url, headers=headers)
            primary_email = None
            if email_resp.ok:
                 emails = email_resp.json()
                 primary_email_obj = next((e for e in emails if e.get('primary') and e.get('verified')), None)
                 if primary_email_obj:
                     primary_email = primary_email_obj.get('email')
                     logger.debug(f"Found primary verified GitHub email: {primary_email}")
                 else:
                     logger.warning(f"Could not find primary verified email for GitHub user {github_login}")
            else:
                logger.warning(f"Failed to fetch emails for GitHub user {github_login}, status: {email_resp.status_code}")

            # Construct standardized user_info dictionary
            user_info = {
                'email': primary_email, # IMPORTANT: Might be None if not found/verified
                'name': github_user.get('name') or github_login, # Use name, fallback to login
                'sub': str(github_user.get('id')), # GitHub user ID as subject
                'picture': github_user.get('avatar_url')
            }

        # --- Post-processing Validation ---
        if not user_info:
            logger.error(f"User info could not be determined for provider {provider_name} after processing.")
            raise ValueError("Failed to retrieve user information from provider.")
        if not user_info.get('email'):
             # Require an email address to proceed
             logger.error(f"Could not retrieve a required email address for user '{user_info.get('name')}' from {provider_name}.")
             raise ValueError(f"Could not retrieve a required email address from {provider_name}.")

        logger.info(f"User info successfully processed for: {user_info.get('email')}")

        # --- Generate Application JWT ---
        app_secret_key = app.config.get('SECRET_KEY')
        if not app_secret_key:
             logger.critical("FATAL: Application SECRET_KEY is not configured in auth-service.")
             raise ValueError("Application JWT secret key is not configured.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        jwt_payload = {
            'sub': user_info['email'], # Use email as the subject claim
            'name': user_info.get('name'),
            'email': user_info['email'],
            'picture': user_info.get('picture'), # Include picture if available
            'provider': provider_name,
            'iat': now_utc, # Issued At
            'exp': now_utc + datetime.timedelta(hours=JWT_EXP_DELTA_HOURS) # Expiration
        }

        logger.debug(f"Generating JWT for user {user_info['email']}")
        app_jwt = jwt.encode(jwt_payload, app_secret_key, algorithm=JWT_ALGORITHM)
        logger.info(f"JWT successfully generated for user {user_info['email']}")

        # Prepare user data for the response (don't send 'sub' unless needed)
        user_response_data = {
            "email": user_info['email'],
            "name": user_info.get('name'),
            "picture": user_info.get('picture')
        }

        return jsonify({"token": app_jwt, "user": user_response_data}), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request Error during token exchange ({provider_name}): {e}", exc_info=True)
        # Check if it was a GitHub API error
        error_msg = "Failed to communicate with authentication provider API."
        status_code = 502 # Bad Gateway might be appropriate
        if provider_name == 'github' and e.response is not None:
             error_msg = f"Error communicating with GitHub API: {e.response.status_code}"
             status_code = e.response.status_code # Pass GitHub's error code if possible
        return jsonify({"error": error_msg}), status_code
    except ValueError as e:
        # Handle specific validation errors (missing email, invalid token, etc.)
        logger.error(f"Validation Error during token exchange ({provider_name}): {e}", exc_info=True)
        return jsonify({"error": f"Failed to process authentication token: {str(e)}"}), 400 # Bad Request
    except Exception as e:
        # Catch-all for other unexpected errors
        logger.error(f"Unexpected error during token exchange ({provider_name}): {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during token processing."}), 500


# --- Health Check (Optional but Recommended) ---
@app.route('/health')
def health_check():
    # Add checks here if needed (e.g., Redis connection)
    return jsonify({"status": "ok"}), 200

# --- Main Execution ---
if __name__ == '__main__':
    # Get host/port from env vars or use defaults
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', '5001'))
    logger.info(f"Starting Auth Service on {host}:{port} (Debug: {app.config['DEBUG']})...")
    # Use debug=False in production, run with a proper WSGI server like Gunicorn/Waitress
    app.run(host=host, port=port, debug=app.config['DEBUG'])