# Stage 1: Build Frontend (Placeholder for Next.js)
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
# If using Next.js, we would do:
# COPY frontend/package*.json ./
# RUN npm install
# COPY frontend/ ./
# RUN npm run build

# Stage 2: Backend & Final Image
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy backend and frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Install python dependencies
WORKDIR /app/backend
RUN uv pip install --system fastapi uvicorn pydantic litellm pydantic-settings pandas numpy

# Expose port
EXPOSE 8000

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV LLM_MOCK=true

# Start uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
