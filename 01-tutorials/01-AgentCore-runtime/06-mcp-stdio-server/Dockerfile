FROM python:3.13-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml .
RUN uv sync
COPY main.py .

EXPOSE 8000 

CMD ["uv", "run", "main.py"]