FROM eclipse-temurin:17-jre

# Download DROID binary
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl unzip python3 && \
    curl -L -o /tmp/droid.zip \
      "https://github.com/digital-preservation/droid/releases/download/droid-6.8.0/droid-binary-6.8.0-bin.zip" && \
    mkdir -p /opt/droid && \
    unzip /tmp/droid.zip -d /opt/droid && \
    rm /tmp/droid.zip && \
    chmod +x /opt/droid/droid.sh && \
    apt-get purge -y curl unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/droid:${PATH}"

# Pre-warm DROID: load signature database and JVM classes at build time
RUN echo "test" > /tmp/warmup.txt && \
    droid.sh -A /tmp/warmup.txt -p /tmp/warmup.droid || true && \
    rm -f /tmp/warmup.txt /tmp/warmup.droid

COPY server.py /app/server.py
EXPOSE 8080
CMD ["python3", "/app/server.py"]
