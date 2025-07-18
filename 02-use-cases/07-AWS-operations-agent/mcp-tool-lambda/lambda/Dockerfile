FROM public.ecr.aws/lambda/python:3.11

# Copy requirements first for better caching
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY mcp-tool-handler.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["mcp-tool-handler.lambda_handler"]
