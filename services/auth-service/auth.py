# # ./services/auth-service/auth.py
# from common import setup_logger
# from flask import Flask, jsonify

# app = Flask(__name__)
# app.config.from_pyfile("config.py")
# logger = setup_logger()


# # OAuth delegation (handled in auth_oauth.py)
# @app.route("/auth/token", methods=["POST"])
# def get_token():
#     # Placeholder for OAuth token validation (use auth_oauth.py)
#     return jsonify({"error": "Authentication required via OAuth"}), 401


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5001, debug=app.config["DEBUG"])
