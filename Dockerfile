FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./

RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .

RUN uv pip install --system --no-cache .

EXPOSE 19999

CMD ["shibaclaw", "gateway"]
