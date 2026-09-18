FROM python:3.12-slim

WORKDIR /kernel

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DESK_ID=tideline

COPY kernel /kernel

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /kernel

EXPOSE 8000

CMD ["uvicorn", "desk_kernel.service.main:app", "--host", "0.0.0.0", "--port", "8000"]
