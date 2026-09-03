FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY tests/requirements.txt ./tests/requirements.txt
RUN pip install --no-cache-dir --requirement tests/requirements.txt

COPY tests ./tests

CMD ["pytest", "-q", "tests"]
