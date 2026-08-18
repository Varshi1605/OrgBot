FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY core ./core
COPY services ./services
COPY simulators ./simulators
COPY ingestion ./ingestion
COPY config ./config

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
