FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

# Install build deps required by some Python packages (kept minimal)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends gcc build-essential libffi-dev \
	&& rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Copy application code
COPY VERSION /VERSION
COPY app.py /
COPY src /src

# Ensure storage and log directories exist and are writable
RUN mkdir -p /storage/logs

EXPOSE 8000

# Runtime command (do not use --reload in production)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
