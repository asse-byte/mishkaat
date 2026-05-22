# =============================================================================
# Mishkaat backend — production image
# =============================================================================
FROM python:3.12-slim AS base

# Minimal system deps; no compiler retained in final image
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --system --gid 1001 mishkaat \
 && useradd  --system --uid 1001 --gid 1001 --no-create-home --home-dir /app mishkaat

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y --auto-remove build-essential \
 && rm -rf /root/.cache

COPY . .

# Drop privileges
USER mishkaat:mishkaat

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8001/api/health || exit 1

# Single-worker default; scale workers via env (each worker independently safe
# because rate-limit state lives in MongoDB now).
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port 8001 --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips=*"]
