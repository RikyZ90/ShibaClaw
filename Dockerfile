FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install system dependencies for C-extensions (needed for arm64/some channels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libolm-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .

RUN if [ -d "ShibaClaw" ]; then mv ShibaClaw shibaclaw; fi
RUN uv pip install --system --reinstall --no-cache ".[telegram]"
RUN uv pip install --system pip-audit

ENV PATH="/opt/tools/bin:$PATH"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 19999 19998 3000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["shibaclaw", "gateway"]
