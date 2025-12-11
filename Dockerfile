# ===============================
# Stage 1: Frontend Build
# ===============================
FROM node:18-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ===============================
# Stage 2: Backend + Final Image
# ===============================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy frontend build → to the folder FastAPI actually serves
COPY --from=frontend-builder /frontend/dist /app/src/ui/static

# Ensure templates folder exists (FastAPI will crash otherwise)
# Your repo uses: src/ui/templates
# So no change needed IF that folder exists in repo.

EXPOSE 9000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers"]