FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install dependencies during build time (network allowed)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy dataset and application code with pre-built offline indexes
COPY data/ /app/data/
COPY coder/ /app/coder/

ENTRYPOINT ["python", "-m", "coder.main"]
