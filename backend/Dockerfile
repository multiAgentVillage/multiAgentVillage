FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
# Phase-one development image: all three entry points use this same image.
RUN python -m pip install --no-cache-dir ".[dev]"
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
