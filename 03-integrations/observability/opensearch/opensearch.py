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

    Data Prepper exposes gRPC endpoints for OTLP ingestion:
      - OTEL_TRACES_ENDPOINT (default http://localhost:21890) for traces
      - OTEL_METRICS_ENDPOINT (default http://localhost:21891) for metrics
    """
    auth = read_secret("opensearch_auth")
    metadata = []
    if auth:
        metadata.append(("authorization", f"Basic {auth}"))

    OTEL_TRACES_ENDPOINT = os.environ.get(
        "OTEL_TRACES_ENDPOINT",
        "http://localhost:21890",  # Data Prepper otel_trace_source default port
    )
    OTEL_METRICS_ENDPOINT = os.environ.get(
        "OTEL_METRICS_ENDPOINT",
        "http://localhost:21891",  # Data Prepper otel_metrics_source default port
    )

    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
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
            endpoint=OTEL_TRACES_ENDPOINT,
            headers=metadata if metadata else None,
            insecure=True,
        )
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=OTEL_METRICS_ENDPOINT,
            headers=metadata if metadata else None,
            insecure=True,
        )
    )
    provider = MeterProvider(
        metric_readers=[reader],
        resource=resource,
    )
    metrics.set_meter_provider(provider)
