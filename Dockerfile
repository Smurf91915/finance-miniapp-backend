FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir .

CMD ["sh", "scripts/start_api.sh"]
