from flask import Flask, jsonify, request
import jwt
from common import setup_logger  # Updated import

app = Flask(__name__)
app.config.from_pyfile('config.py')
logger = setup_logger()

# Dummy user store (replace with MongoDB or similar in production)
users = {'user@example.com': 'password123'}

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if users.get(email) == password:
        token = jwt.encode({'email': email}, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'token': token}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=app.config['DEBUG'])