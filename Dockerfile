FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./

RUN mkdir shibaclaw && \
    touch shibaclaw/__init__.py && \
    uv pip install --system --no-cache .

COPY . .

RUN uv pip install --system --no-cache .

EXPOSE 19999

CMD ["shibaclaw", "gateway"]
