FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY kernel /kernel
COPY emberline/backend/pyproject.toml /app/pyproject.toml
COPY emberline/backend/app /app/app
COPY emberline/backend/fixtures /app/fixtures

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /kernel \
    && pip install --no-cache-dir .

EXPOSE 8000

# Not root: the public Emberline API (state is in Postgres). uid 10001 owns only what it writes (nothing on disk).
ENV HOME=/tmp
USER 10001:10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
