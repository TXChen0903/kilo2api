FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY core/ core/
COPY provider.py config.py main.py ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml ./
COPY core/ core/
COPY provider.py config.py main.py ./
COPY core/static/ static/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 9090

CMD ["uv", "run", "main.py"]
