FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV CP_DB_PATH=/data/claimpassport.db CP_UPLOAD_DIR=/data/uploads
VOLUME /data
EXPOSE 8000
# One worker: the background scheduler runs inside it. For several workers, set CP_SCHEDULER=0 and run one scheduler process.
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8000", "wsgi:app"]
