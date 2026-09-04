FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY tests/api/requirements.txt ./tests/api/requirements.txt
RUN pip install --no-cache-dir --requirement tests/api/requirements.txt

COPY tests/api ./tests/api

CMD ["python", "tests/api/run_tests.py"]
