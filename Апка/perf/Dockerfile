FROM python:3.12-slim

WORKDIR /app

COPY perf/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY perf ./perf

EXPOSE 8089

CMD ["locust", "-f", "/app/perf/locustfile.py", "--host=http://localhost", "--web-host=0.0.0.0", "--web-port=8089"]
