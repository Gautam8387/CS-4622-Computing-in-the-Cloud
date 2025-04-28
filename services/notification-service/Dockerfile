# ./services/notification-service/Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY common ./common
COPY notification-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY notification-service/ .

CMD ["python", "notify.py"]