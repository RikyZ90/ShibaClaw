FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./

RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .

RUN if [ -d "ShibaClaw" ]; then mv ShibaClaw shibaclaw; fi
RUN uv pip install --system --reinstall --no-cache ".[telegram]"
RUN uv pip install --system pip-audit


RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/tools/bin:$PATH"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 19999 19998 3000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["shibaclaw", "gateway"]
