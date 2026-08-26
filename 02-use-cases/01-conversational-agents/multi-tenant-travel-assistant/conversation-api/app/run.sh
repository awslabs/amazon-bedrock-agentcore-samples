#!/bin/bash
# LWA convention: the Lambda `handler` is this script, and LWA runs our HTTP server behind it.
# `exec` so uvicorn becomes PID 1 and receives Lambda's signals directly.
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
