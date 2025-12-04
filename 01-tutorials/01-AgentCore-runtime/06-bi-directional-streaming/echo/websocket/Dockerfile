FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy agent file
COPY websocket_echo_agent.py ./

# Expose port
EXPOSE 8080
EXPOSE 8081

# Run application directly
CMD ["python", "websocket_echo_agent.py"]
