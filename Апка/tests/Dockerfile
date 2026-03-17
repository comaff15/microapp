FROM python:3.12-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY tests/requirements.txt /app/tests/requirements.txt
RUN pip install --no-cache-dir -r /app/tests/requirements.txt

# Playwright browsers (chromium) for e2e
RUN python -m playwright install --with-deps chromium

COPY . /app

ENV PYTHONPATH=/app

CMD ["pytest", "-c", "tests/pytest.ini", "-q", "--alluredir=/app/allure-results"]
