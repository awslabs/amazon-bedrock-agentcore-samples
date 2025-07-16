FROM public.ecr.aws/docker/library/python:3.11-slim-bullseye

# Install Lambda Web Adapter as extension - MATCH WORKING EXAMPLE
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

# Run Python directly (not as Lambda handler)
CMD ["python", "main.py"]
