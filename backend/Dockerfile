FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY assets ./assets
COPY alembic ./alembic
COPY alembic.ini .
RUN useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser /data
USER appuser
ENV STORAGE_ROOT=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
