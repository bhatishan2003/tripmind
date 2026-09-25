FROM python:3.11-slim

WORKDIR /code

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
