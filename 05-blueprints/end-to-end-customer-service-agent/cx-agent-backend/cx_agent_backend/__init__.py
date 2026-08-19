"""CX demo agent package including agent definition and AgentCore-compatible REST server"""

# TODO: Review how log level configuration can fit together with other settings
# We need to configure logging here during module initialization, **before** other local and
# external imports start creating loggers with their own default levels, formats, etc.
import logging
from os import environ
import structlog

# Basic terminal logging:
logging.basicConfig(
    level=environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Structured logging:
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
