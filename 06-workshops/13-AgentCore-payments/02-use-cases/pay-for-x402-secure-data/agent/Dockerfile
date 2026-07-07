FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    OTEL_SERVICE_NAME=pay-for-x402-secure-data \
    OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental,gen_ai_tool_definitions

COPY agent/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY agent/. /app/

EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
