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

# Trust the corporate TLS-inspecting proxy (Zscaler) some devs build behind,
# so the Playwright CDN download below doesn't fail with an untrusted cert.
COPY certs/zscaler-bundle.crt /usr/local/share/ca-certificates/zscaler-bundle.crt
RUN update-ca-certificates

# Install Playwright browsers (--use-system-ca points Node at the system CA
# store above, since Node otherwise uses its own bundled cert list)
RUN NODE_OPTIONS="--use-system-ca" playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Install the package (with trusted-host for macOS Docker SSL issues)
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .

# Expose port
EXPOSE 8000

# Start server (migrations are run via fly.toml release_command)
# --proxy-headers trusts X-Forwarded-Proto from Fly's edge, so generated URLs
# use https:// instead of http:// (without it, forms like the admin login
# redirect on every submit). --forwarded-allow-ips is needed because Fly's
# edge doesn't forward from 127.0.0.1 (uvicorn's default trusted source) —
# safe here since this internal port is only reachable via Fly's own proxy.
CMD uvicorn cinescout.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
