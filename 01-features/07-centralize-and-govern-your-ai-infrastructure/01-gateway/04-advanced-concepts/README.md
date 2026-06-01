# Advanced Concepts

Advanced gateway patterns including interceptors, security controls, observability, and custom tool behaviors for Amazon Bedrock AgentCore gateway.

## Tutorials

| Section | Description |
| :--- | :--- |
| [fine-grain-access-control](fine-grain-access-control/) | JWT scope-based fine-grained access control with REQUEST + RESPONSE interceptors |
| [prevent-sql-injection](prevent-sql-injection/) | Detect and block SQL injection in tool inputs with a REQUEST interceptor |
| [sensative-data-masking](sensative-data-masking/) | Mask PII in tool responses using a RESPONSE interceptor + Bedrock Guardrails |
| [header-query-propagation](header-query-propagation/) | Propagate custom HTTP headers and query parameters from clients to targets |
| [header-query-propagation/custom-header-query](header-query-propagation/custom-header-query/) | Allowlisted headers, query params, interceptor precedence rules |
| [header-query-propagation/token-passthrough](header-query-propagation/token-passthrough/) | Pass client Authorization token through to targets via interceptor |
| [semantic-search-tool](semantic-search-tool/) | Semantic search across 300+ tools for improved agent latency |
| [gateway-observability](gateway-observability/) | CloudWatch metrics, logs, traces, and CloudTrail auditing |

## Documentation

- [AgentCore gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [gateway Interceptors](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors.html)
- [Header Propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
