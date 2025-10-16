# Advanced Observability Concepts

This section covers advanced observability patterns and techniques for Amazon Bedrock AgentCore, helping you implement sophisticated customized monitoring and debugging capabilities.

## Available Tutorials

### 01-custom-span-creation/
- **Notebook**: `Custom_Span_Creation.ipynb`
- **Description**: Learn to create custom spans for detailed operation tracing
- **Features**: Manual span creation, custom attributes
- **Use Cases**: Fine-grained monitoring, debugging

## What You'll Learn

- **Custom Span Creation**: Add detailed tracing to specific operations
- **Span Attributes**: Enrich traces with custom metadata
- **Nested Spans**: Create hierarchical trace structures
- **Performance Monitoring**: Identify bottlenecks in agent workflows
- **Error Tracking**: Capture and trace exceptions and failures

## Getting Started

1. Navigate to the tutorial directory
2. Copy `.env.example` to `.env` and configure:
   - AWS credentials
   - CloudWatch log group settings
   - OpenTelemetry configuration
3. Enable CloudWatch Transaction Search in your AWS region
4. Install dependencies: `pip install -r requirements.txt`
5. Open and run the Jupyter notebook

## Prerequisites

- Understanding of basic OpenTelemetry concepts
- Familiarity with Amazon CloudWatch
- Experience with agent frameworks (recommended)
- AWS account with appropriate permissions

## Advanced Patterns Covered

- **Manual Instrumentation**: When and how to add custom spans
- **Custom Metrics**: Creating domain-specific measurements

## Cleanup

After completing tutorials:
1. Delete CloudWatch log groups created during examples
2. Remove any test resources
3. Clean up environment configuration files