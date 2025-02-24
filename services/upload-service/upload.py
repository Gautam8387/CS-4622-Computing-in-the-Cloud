from flask import Flask, request, jsonify
from common import upload_to_s3, setup_logger  # Updated import

app = Flask(__name__)
app.config.from_pyfile('config.py')
logger = setup_logger()

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    s3_key = f"raw/{file.filename}"
    upload_to_s3(file, s3_key)
    logger.info(f"Uploaded {file.filename} to S3 as {s3_key}")
    return jsonify({'message': 'File uploaded', 's3_key': s3_key}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=app.config['DEBUG'])