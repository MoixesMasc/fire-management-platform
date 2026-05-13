# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.11-alpine AS builder

WORKDIR /build

# Install build dependencies (needed for some native Python packages)
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

COPY services/incidents/requirements.txt .

# Install into a target directory for clean copy to final stage
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-alpine AS runtime

# Non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY shared/ ./shared/
COPY services/incidents/ ./services/incidents/
COPY services/__init__.py ./services/

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV AWS_REGION=us-east-1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "services.incidents.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]