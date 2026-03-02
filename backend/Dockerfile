# Backend Dockerfile for Fly.io deployment
FROM python:3.13-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip (with trusted-host for macOS Docker SSL issues)
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade pip setuptools wheel

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies (with trusted-host for macOS Docker SSL issues)
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Install the package (with trusted-host for macOS Docker SSL issues)
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .

# Expose port
EXPOSE 8000

# Start server (migrations are run via fly.toml release_command)
CMD uvicorn cinescout.main:app --host 0.0.0.0 --port 8000
