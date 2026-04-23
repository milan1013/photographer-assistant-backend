FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app && mkdir -p /app/storage && chown appuser:appuser /app/storage
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run migrations then start server
CMD ["sh", "-c", "uv run python -m alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
