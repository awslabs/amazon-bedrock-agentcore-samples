import os


def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception:
        print("No credentials file found, falling back to environment variable")
        return os.environ.get("OPENSEARCH_AUTH", "")


def init():
    """Initialize OpenTelemetry SDK to export traces and metrics to OpenSearch via Data Prepper.

    Data Prepper is an OpenSearch community project that accepts OTLP data
    and writes it to OpenSearch indices for Trace Analytics.

    By default, Data Prepper listens on:
      - Port 21890 for traces (OTLP/HTTP)
      - Port 21891 for metrics (OTLP/HTTP)

    Configure OTEL_ENDPOINT to point to your Data Prepper instance.
    """
    auth = read_secret("opensearch_auth")
    headers = {}
    if auth:
        headers["Authorization"] = f"Basic {auth}"

    OTEL_ENDPOINT = os.environ.get(
        "OTEL_ENDPOINT",
        "http://localhost:4318",  # Data Prepper OTLP HTTP endpoint
    )

    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create(
        {
            "service.name": "agent-core-samples",
        }
    )

    provider = TracerProvider(resource=resource)
    processor = SimpleSpanProcessor(
        OTLPSpanExporter(
            endpoint=f"{OTEL_ENDPOINT}/v1/traces",
            headers=headers if headers else None,
        )
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=f"{OTEL_ENDPOINT}/v1/metrics",
            headers=headers if headers else None,
        )
    )
    provider = MeterProvider(
        metric_readers=[reader],
        resource=resource,
    )
    metrics.set_meter_provider(provider)
