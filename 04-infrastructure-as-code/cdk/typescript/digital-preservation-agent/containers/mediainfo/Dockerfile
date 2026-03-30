FROM alpine:3.20

RUN apk add --no-cache python3 mediainfo

COPY server.py /app/server.py
EXPOSE 8081
CMD ["python3", "/app/server.py"]
