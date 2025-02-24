FROM python:3.9-slim

WORKDIR /app
COPY ../common ./common
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "notify.py"]