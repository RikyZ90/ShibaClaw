# syntax=docker/dockerfile:1
# STAGE 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Evita che uv crei un virtualenv nel percorso predefinito, 
# installa invece i pacchetti nel sistema o in una cartella specifica
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libolm-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia solo i file di dipendenze per sfruttare la cache di Docker
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --no-install-project --no-dev --extra telegram

# Copia il resto del codice e installa il progetto
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --extra telegram

# STAGE 2: Final Image
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libolm3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia l'ambiente virtuale creato da uv dallo stage builder
COPY --from=builder /app/.venv /app/.venv

# Assicura che l'app usi il virtualenv di uv
ENV PATH="/app/.venv/bin:$PATH"

# Copia l'applicazione e i file necessari
COPY . .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 19999 19998 3000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["shibaclaw", "gateway"]
