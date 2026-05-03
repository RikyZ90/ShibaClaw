# syntax=docker/dockerfile:1
# STAGE 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Install build dependencies without upgrade to speed up the build stage
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libolm-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Use cache mount for uv to speed up dependency installation
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r pyproject.toml

COPY . .
# Fix directory naming if necessary
RUN if [ -d "ShibaClaw" ]; then mv ShibaClaw shibaclaw; fi

# Install the package and audit tools
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --reinstall --no-cache ".[telegram]" && \
    uv pip install --system pip-audit

# STAGE 2: Final Image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install runtime dependencies and perform security upgrade
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libolm3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to fix known CVEs (e.g., CVE-2026-3219)
RUN uv pip install --system --upgrade pip

# Copy installed packages and application from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Remnant or specific tool path
ENV PATH="/opt/tools/bin:$PATH"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 19999 19998 3000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["shibaclaw", "gateway"]
