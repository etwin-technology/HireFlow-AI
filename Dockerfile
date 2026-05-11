FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# System dependencies required by Playwright + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2-dev \
        libxslt-dev \
        libffi-dev \
        libssl-dev \
        libnss3 \
        libxss1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        libgbm-dev \
        libxshmfence1 \
        fonts-liberation \
        curl \
        ca-certificates \
        wget \
        gnupg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Playwright browser binaries
RUN python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8765

# Headless API by default; override CMD for GUI / headless scrape.
CMD ["python", "-m", "app.main", "--api"]
