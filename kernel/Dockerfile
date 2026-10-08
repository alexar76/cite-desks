FROM python:3.12-slim

WORKDIR /kernel

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DESK_ID=tideline

COPY kernel /kernel

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /kernel

EXPOSE 8000

# Not root: a public desk API (state is in Postgres). uid 10001 owns only what it writes (nothing on disk).
ENV HOME=/tmp
USER 10001:10001

CMD ["uvicorn", "desk_kernel.service.main:app", "--host", "0.0.0.0", "--port", "8000"]
