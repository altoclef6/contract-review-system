FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-chi-sim libreoffice-writer fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml alembic.ini ./
RUN pip install --no-cache-dir -r requirements.txt
COPY migrations ./migrations
COPY src ./src
COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN chmod +x /usr/local/bin/backend-entrypoint

EXPOSE 8000
CMD ["backend-entrypoint"]
