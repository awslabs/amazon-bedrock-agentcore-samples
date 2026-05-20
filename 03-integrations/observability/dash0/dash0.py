import os


def init():
    auth_token = os.environ.get("DASH0_AUTH_TOKEN", "")
    if not auth_token:
        print("Warning: DASH0_AUTH_TOKEN not set. Traces will not be sent to Dash0.")

    otlp_base = os.environ.get(
        "DASH0_OTLP_ENDPOINT",
        "https://ingress.us-west-2.aws.dash0.com",
    ).rstrip("/")
    dataset = os.environ.get("DASH0_DATASET", "agentcore")
    service_name = os.environ.get("OTEL_SERVICE_NAME", "agentcore-dash0-demo")

    headers = {"Authorization": f"Bearer {auth_token}"}
    if dataset:
        headers["Dash0-Dataset"] = dataset

    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": service_name})

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        SimpleSpanProcessor(
            OTLPSpanExporter(
                endpoint=f"{otlp_base}/v1/traces",
                headers=headers,
            )
        )
    )
    trace.set_tracer_provider(trace_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=f"{otlp_base}/v1/metrics",
            headers=headers,
        )
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    print(f"Dash0 observability configured (service: {service_name}, dataset: {dataset})")
