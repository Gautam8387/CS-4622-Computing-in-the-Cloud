from flask import jsonify, request
from common import upload_to_s3, add_transcoding_job

def init_routes(app):
    @app.route('/upload', methods=['POST'])
    def upload_file():
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        email = request.form.get('email')  # Expect email in form data
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        if file.filename == '' or not allowed_file(app, file.filename):
            return jsonify({'error': 'Invalid file'}), 400
        
        # Upload to S3
        s3_key = f"raw/{file.filename}"
        upload_to_s3(file, s3_key)
        
        # Queue transcoding job with email
        job_id = add_transcoding_job(s3_key, email)
        return jsonify({'job_id': job_id}), 202

    @app.route('/status/<job_id>', methods=['GET'])
    def job_status(job_id):
        # Placeholder for job status check via Redis (could integrate Celery result)
        return jsonify({'job_id': job_id, 'status': 'pending'}), 200

def allowed_file(app, filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']