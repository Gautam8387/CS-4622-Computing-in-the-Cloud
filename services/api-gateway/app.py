# ./services/api-gateway/app.py
from common import setup_logger
from flask import Flask
from routes import init_routes

app = Flask(__name__)
logger = setup_logger()

# Load configuration
app.config.from_pyfile("config.py")

# Initialize routes
init_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
