FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "uv run python -m alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
