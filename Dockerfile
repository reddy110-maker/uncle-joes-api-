FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY . /app

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
