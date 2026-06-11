#!/bin/bash
# Build a deployable Lambda ZIP that bundles the Strands agent and the
# AWS OTel Python instrumentation (aws-opentelemetry-distro).
#
# The opentelemetry-instrument binary is copied from the pip-installed package
# to the ZIP root so that AWS_LAMBDA_EXEC_WRAPPER=/var/task/opentelemetry-instrument
# can reference it without relying on the ADOT managed layer path.
#
# Usage (replace 'finch' with 'docker' if using Docker):
#   chmod +x build.sh
#   ./build.sh

set -e

echo "Building Lambda deployment package..."

# Use the SAM build container for a Lambda-compatible Python 3.13 environment.
# Replace 'finch' with 'docker' if you are using Docker instead of Finch.
finch run --rm -v "$PWD":/var/task public.ecr.aws/sam/build-python3.13:latest-x86_64 /bin/sh -c "
  rm -rf package package.zip
  mkdir -p package
  pip install --quiet -r requirements.txt -t /var/task/package
  cd /var/task/package
  cp ./bin/opentelemetry-instrument .
  zip -r9q /var/task/package.zip .
  cd /var/task
  zip -g package.zip lambda_agent.py
"

echo "Build complete: package.zip"
