FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-chi-sim libreoffice-writer fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml alembic.ini ./
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.1.2,<27" \
    && pip install --no-cache-dir --only-binary=:all: -r requirements.txt
COPY migrations ./migrations
COPY src ./src
COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN addgroup --system --gid 10001 contractreview \
    && adduser --system --uid 10001 --ingroup contractreview contractreview \
    && mkdir -p /app/data \
    && chown -R contractreview:contractreview /app \
    && chmod +x /usr/local/bin/backend-entrypoint

EXPOSE 8000
USER contractreview
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/api/v1/health/ready', headers={'Host': os.environ['TRUSTED_HOSTS'].split(',')[0]}); urllib.request.urlopen(request, timeout=3)" || exit 1
CMD ["backend-entrypoint"]
