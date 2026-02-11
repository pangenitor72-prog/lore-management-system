# ===============================
# LMS API Dockerfile
# ===============================
# Simplified for MVP deployment - API only
# Frontend can be added back later

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY docs/ ./docs/
COPY CLAUDE.md ./

# Cache-bust for data directory (changes with each deploy)
ARG CACHEBUST=1
# Copy data directory (lore bases, etc.)
COPY data/ ./data/

# Copy frontend dist (self-contained HTML UI)
COPY frontend/dist/ ./frontend/dist/

# Copy frontend games (mini-games)
COPY frontend/games/ ./frontend/games/

EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')" || exit 1

CMD ["uvicorn", "src.mantle.api.routes:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers"]
