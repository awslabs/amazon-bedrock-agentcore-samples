#!/bin/bash
# Build a Lambda-compatible deployment ZIP.
#
# Only strands-agents (and its dependencies) are bundled.
# The ADOT instrumentation layer is attached separately in the Lambda console —
# do NOT pip-install opentelemetry or aws-opentelemetry-distro here.
#
# Usage (replace 'finch' with 'docker' if using Docker):
#   chmod +x build.sh
#   ./build.sh
#
# Output: package.zip  (upload this to your Lambda function)

set -e

echo "Building Lambda deployment package..."

# Build inside the SAM container to ensure native deps compile for the Lambda runtime.
# Replace 'finch' with 'docker' if you are using Docker.
finch run --rm -v "$PWD":/var/task public.ecr.aws/sam/build-python3.13:latest-x86_64 /bin/sh -c "
  rm -rf package package.zip
  mkdir -p package
  pip install --quiet -r requirements.txt -t /var/task/package
  cd /var/task/package
  zip -r9q /var/task/package.zip .
  cd /var/task
  zip -g package.zip lambda_agent.py
"

echo "Build complete → package.zip"
