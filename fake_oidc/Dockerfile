FROM python:3.12-slim

WORKDIR /fake-oidc

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
