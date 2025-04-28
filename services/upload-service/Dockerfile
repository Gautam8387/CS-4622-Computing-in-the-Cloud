# ./services/upload-service/Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY common ./common
COPY upload-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY upload-service/ .

EXPOSE 5002
CMD ["python", "upload.py"]