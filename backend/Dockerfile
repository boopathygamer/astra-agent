# ── Build stage ──────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Runtime system deps (for playwright, psutil, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data reports

# Expose the API port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run with uvicorn
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--log-level", "info"]
