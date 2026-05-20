FROM python:3.10-slim

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    # Playwright browser system dependencies
    libatk-bridge2.0-0 \
    libxkbcommon-x11-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser engines and system dependencies
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# Pre-download spaCy NLP dictionary model to save runtime time
RUN python -m spacy download en_core_web_sm

# Create storage directory for downloaded images
RUN mkdir -p storage/images

# Copy source code files
COPY . .

# Expose FastAPI HTTP server port
EXPOSE 8000

# Default command launches FastAPI backend
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
