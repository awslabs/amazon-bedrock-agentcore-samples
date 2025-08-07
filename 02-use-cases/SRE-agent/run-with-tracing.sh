#!/bin/bash

# OpenTelemetry configuration for SRE Agent with Jaeger
export OTEL_SERVICE_NAME="sre-agent"
export OTEL_RESOURCE_ATTRIBUTES="service.name=sre-agent,service.version=1.0.0,deployment.environment=dev,user.id=${USER_ID:-unknown}"
export OTEL_LOGS_EXPORTER=none  # Jaeger doesn't support logs
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=none  # Jaeger doesn't visualize metrics
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
export OTEL_INSTRUMENTATION_LANGCHAIN_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
export OTEL_EXPORTER_OTLP_PROTOCOL="grpc"

# Enable more detailed tracing
export OTEL_PYTHON_EXCLUDED_URLS="health,metrics"
export OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT=12000

echo "🔍 Starting SRE Agent with OpenTelemetry tracing..."
echo "📊 Service Name: ${OTEL_SERVICE_NAME}"
echo "👤 User ID: ${USER_ID:-not set}"
echo "🌐 Jaeger UI: http://localhost:16686"
echo ""

# Run with opentelemetry-instrument
opentelemetry-instrument sre-agent "$@"