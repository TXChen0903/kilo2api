FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY core/ core/
COPY provider.py config.py main.py ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY core/ core/
COPY provider.py config.py main.py ./

ENV PATH="/app/.venv/bin:$PATH"
ENV ACCOUNTS_DIR=/app/data
ENV HOST=0.0.0.0
ENV PORT=9090
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

VOLUME /app/data

EXPOSE 9090

CMD ["python", "main.py"]
