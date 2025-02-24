import os

import jwt
from authlib.integrations.flask_client import OAuth
from common import setup_logger
from flask import Flask, jsonify, request, url_for

app = Flask(__name__)
app.config.from_pyfile("config.py")
logger = setup_logger()

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://accounts.google.com/o/oauth2/token",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    refresh_token_url=None,
    client_kwargs={"scope": "email profile"},
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:5001/auth/callback"),
)

github = oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    refresh_token_url=None,
    client_kwargs={"scope": "user:email"},
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:5001/auth/callback"),
)


@app.route("/auth/login/google")
def login_google():
    redirect_uri = url_for("auth_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/login/github")
def login_github():
    redirect_uri = url_for("auth_callback", _external=True)
    return github.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    token = (
        google.authorize_access_token()
        if "google" in request.url
        else github.authorize_access_token()
    )
    if token:
        # Get user info
        if "google" in request.url:
            resp = google.get("https://www.googleapis.com/oauth2/v2/userinfo")
        else:
            resp = github.get("https://api.github.com/user")
        user = resp.json()
        email = user.get("email", user.get("login"))

        # Generate JWT token
        jwt_token = jwt.encode(
            {"email": email}, app.config["SECRET_KEY"], algorithm="HS256"
        )
        return jsonify({"token": jwt_token, "email": email}), 200
    return jsonify({"error": "Authentication failed"}), 401


@app.route("/auth/logout")
def logout():
    # Clear token in Redis or session (implement Redis storage if needed)
    return jsonify({"message": "Logged out"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=app.config["DEBUG"])
