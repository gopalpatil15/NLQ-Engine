# ─────────────────────────────────────────────────────────────
# NLQ-Engine Dockerfile
# Build:  docker build -t nlq-engine .
# Run:    docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... nlq-engine
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first (cached layer if requirements unchanged)
COPY backend/requirements.txt ./backend/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the project
COPY . .

# Expose the application port
EXPOSE 8000

# Start the application (bound to all interfaces for cloud deployment)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
