# --------------------------------------------------------------------------
# Bidar auth server runtime image
#
# Runtime dependencies only, installed from the uv lock export, run as a
# non-root user. Build dependencies stay in the builder stage.
# --------------------------------------------------------------------------

# python:3.12-slim-bookworm resolved on 2026-09-18. Pinned by digest so the
# image content cannot change under a moving tag; refresh it deliberately.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt is generated from uv.lock:
#   uv export --no-hashes --no-dev --no-emit-project -o requirements.txt
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin bidar

COPY --from=builder /opt/venv /opt/venv
COPY --chown=bidar:bidar src/ ./src/
COPY --chown=bidar:bidar migrations/ ./migrations/

USER bidar

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8001/health || exit 1

# Run the application
CMD ["python", "-m", "src.main"]
