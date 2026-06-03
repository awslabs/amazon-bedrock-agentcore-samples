# Build stage — Chainguard's dev image has a shell + apk; default user is nonroot,
# switch to root only for installing deps into /app.
FROM cgr.dev/chainguard/python:3.13-dev AS build
USER root

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Make the venv readable by the nonroot UID (65532) used by the runtime image.
RUN chown -R 65532:65532 /app

# Runtime — distroless Python: no shell, no package manager, nonroot by default.
FROM cgr.dev/chainguard/python:3.13

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=build --chown=65532:65532 /app /app

USER 65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]
# Clear the base image's ENTRYPOINT so ECS run-task command overrides (e.g. the
# DB bootstrap script) replace the full process. With absolute paths in CMD
# we don't depend on PATH resolution either.
ENTRYPOINT []
CMD ["/app/.venv/bin/uvicorn", "ecommerce.main:app", "--host", "0.0.0.0", "--port", "8000"]
