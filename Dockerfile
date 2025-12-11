# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential curl

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy frontend build from stage 1
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

EXPOSE 9000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers"]
