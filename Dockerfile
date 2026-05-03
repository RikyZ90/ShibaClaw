# STAGE 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libolm-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Install dependencies into a virtualenv or direct to system in builder
# We'll use --system but since it's a builder stage it's fine
RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .
RUN if [ -d "ShibaClaw" ]; then mv ShibaClaw shibaclaw; fi
RUN uv pip install --system --reinstall --no-cache ".[telegram]"
RUN uv pip install --system pip-audit

# STAGE 2: Final Image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install ONLY runtime dependencies (no build tools)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libolm3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to fix CVE-2025-8869 and CVE-2026-3219
RUN uv pip install --system --upgrade pip


# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

ENV PATH="/opt/tools/bin:$PATH"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 19999 19998 3000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["shibaclaw", "gateway"]
