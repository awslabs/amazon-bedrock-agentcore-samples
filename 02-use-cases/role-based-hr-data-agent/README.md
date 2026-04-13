# Role-Based HR Data Agent

> [!IMPORTANT]
> This sample is for experimental and educational purposes only. It demonstrates concepts and techniques but is not intended for direct use in production environments.

> [!IMPORTANT]
> This sample uses synthetic HR data for demonstration purposes only. No real employee data is processed.

**Important:**
- This application **is not intended** for direct use in production environments.
- The code and architecture presented here are examples and may not meet all security, scalability, or compliance requirements for your specific use case.
- Before deploying any similar system in a production environment, it is crucial to:
  - Conduct thorough testing and security audits
  - Ensure compliance with all relevant regulations and industry standards
  - Optimize for your specific performance and scalability needs
  - Implement proper error handling, logging, and monitoring
  - Follow all AWS best practices for production deployments

A role-based HR data access agent with automatic **scope-based field redaction** using Amazon Bedrock AgentCore. The agent enforces data access policies based on each caller's OAuth 2.0 scopes — without changing application code.

**Key capabilities:**
- **AgentCore Runtime** — hosts the Strands Agent; receives user prompts and drives MCP tool calls via the Gateway
- **AgentCore Gateway** — central policy enforcement point; routes every `tools/list` and `tools/call` through interceptors and Cedar
- **Request Interceptor** — decodes JWT and injects tenant context on every `tools/call`
- **Cedar Policy Engine** — Allow/Deny per tool based on OAuth scopes
- **Response Interceptor** — hides tools from `tools/list` and redacts fields on `tools/call` responses
- **Multi-tenant isolation** — tenant resolved from OAuth `client_id`; no custom JWT claims needed
- **Cognito OAuth 2.0** — `client_credentials` with custom scopes per persona

> **Note:** This sample uses AWS Lambda as the AgentCore Gateway target.

![Architecture](docs/screenshots/full-architecture.png)

| # | Step |
|---|---|
| 1 | Application sends a prompt to AgentCore Runtime with an inbound auth token |
| 2 | Runtime obtains a scoped JWT from Cognito (`client_credentials` flow) |
| 3 | Strands Agent sends an MCP request (`tools/list` or `tools/call`) to AgentCore Gateway with the JWT in the header |
| 4 | Gateway forwards the request to the **Request Interceptor Lambda** |
| 5 | Request Interceptor decodes the JWT, injects `tenantId` into tool arguments, and returns the transformed request |
| 6 | Gateway evaluates the **Cedar Policy Engine** — Allow or Deny based on OAuth scopes |
| 7 | Gateway calls the **Lambda target** (HR Data Provider) with the transformed request, using AgentCore Identity for outbound auth |
| 8 | Lambda returns the full (unredacted) response |
| 9 | Gateway passes the response to the **Response Interceptor Lambda** |
| 10 | Response Interceptor applies field-level redaction and filters tool discovery by scope; transformed response returned to the Runtime |

## Demo

| HR Manager — full access | Employee — all sensitive fields redacted |
|:---:|:---:|
| ![HR Manager](docs/screenshots/hr-manager.png) | ![Employee](docs/screenshots/employee.png) |

> Same query, same agent, different OAuth scopes — field redaction applied automatically by the Response Interceptor.

> See [per-persona request flow](docs/diagrams/flow.md) for a detailed sequence diagram with per-persona field redaction steps.

## Reference

### Scope → Field Mapping

The Lambda target returns full unredacted records for every caller. The Response Interceptor applies field-level redaction based on the caller's OAuth scopes — ensuring sensitive fields never reach the agent or the user unless the persona has explicit permission. This mapping is defined in `_redact_employee()` in [`prerequisite/lambda/interceptors/response_interceptor.py`](prerequisite/lambda/interceptors/response_interceptor.py). To extend redaction to other data sources (DynamoDB, RDS, S3), update the field lists in that function — the Gateway interceptor pattern applies identically regardless of what the Lambda target reads from.

| Scope | Redacted fields |
|---|---|
| `hr-dlp-gateway/pii` | email, phone, personal_phone, emergency_contact |
| `hr-dlp-gateway/address` | address, city, state, zip_code |
| `hr-dlp-gateway/comp` | salary, bonus, stock_options, pay_grade, benefits_value, compensation_history |

### Persona Access Matrix

Step 2 (`prereq.sh`) creates a Cognito User Pool with a resource server (`hr-dlp-gateway`) that defines four custom OAuth scopes — `read`, `pii`, `address`, and `comp` — and provisions one app client per persona with a fixed `AllowedOAuthScopes` list. Each persona gets a `client_id` and `client_secret` stored in SSM; the agent fetches a token via `client_credentials` flow using those credentials. The Gateway enforces what tools are visible and what fields are returned based on the scopes present in the token.

| Persona | Scopes | Tools visible | Salary | Email | Address |
|---|---|---|---|---|---|
| HR Manager | read, pii, address, comp | 3 | Visible | Visible | Visible |
| HR Specialist | read, pii | 2 | `[REDACTED]` | Visible | `[REDACTED]` |
| Employee | read | 1 | `[REDACTED]` | `[REDACTED]` | `[REDACTED]` |
| Admin | read, pii, address, comp | 3 | Visible | Visible | Visible |

## Prerequisites

- AWS account with Amazon Bedrock AgentCore access (us-east-1)
- **Claude Haiku 4.5** enabled via cross-region inference (CRIS) in your account
- Python 3.10+
- AWS CLI configured (`aws configure`)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

### Step 1: Clone and install

```bash
git clone https://github.com/awslabs/agentcore-samples.git
cd agentcore-samples/02-use-cases/role-based-hr-data-agent

uv sync
```

### Step 2: Deploy infrastructure

Packages Lambda functions and deploys CloudFormation stacks for Lambda, IAM, and Cognito. Stores all resource IDs in SSM under `/app/hrdlp/*`.

```bash
bash scripts/prereq.sh --region us-east-1 --env dev
```

### Step 3: Create the AgentCore Gateway

Creates the Gateway with JWT authorizer, Lambda target (3 HR tools), and request/response interceptors. The Lambda target **must** be attached before Step 4 — Cedar builds its policy schema from the registered tool names.

```bash
python scripts/agentcore_gateway.py create --config prerequisite/prereqs_config.yaml
```

### Step 4: Create the Cedar Policy Engine

Attaches the Cedar Policy Engine and creates the three HR authorization policies. Uses a two-phase `update_gateway` approach: Phase A attaches the engine **without interceptors** so Cedar's internal schema initialization call succeeds, then Phase B restores the interceptors once policies are ACTIVE.

```bash
python scripts/create_cedar_policies.py --region us-east-1 --env dev
```

Default mode is `LOG_ONLY`. Switch to enforcement for production:

```bash
python scripts/create_cedar_policies.py --mode ENFORCE
```

### Step 5: Deploy the AgentCore Runtime

```bash
bash scripts/package_runtime.sh

BUCKET=$(aws ssm get-parameter --name /app/hrdlp/deploy-bucket --query Parameter.Value --output text)
aws s3 cp dist/runtime.zip s3://${BUCKET}/hr-data-agent/runtime.zip

python scripts/agentcore_agent_runtime.py create
```

### Step 6: Run the Streamlit app

```bash
streamlit run app.py
```

Open http://localhost:8501. Select a persona, click **Get OAuth Token**, then ask a question such as *"Show me John Smith's compensation"*. Switch personas to see field redaction applied automatically.

## Testing

> **Note:** Cedar defaults to `LOG_ONLY` mode — policies log decisions but do not block requests. Tests will pass in either mode; switch to `ENFORCE` only when ready for production.

### Verify field redaction

```bash
python test/test_dlp_redaction.py
```

Expected output:

```
Testing persona: hr-manager      →  PASS  (salary visible, email visible)
Testing persona: hr-specialist   →  PASS  (salary redacted, email visible)
Testing persona: employee        →  PASS  (salary redacted, email redacted)
Testing persona: admin           →  PASS  (salary visible, email visible)
```

### Test the full agent

```bash
python test/test_agent.py --persona hr-manager --prompt "Show me John Smith's compensation"
python test/test_agent.py --persona employee --prompt "Show me John Smith's compensation"
```

### Test the Gateway directly

```bash
python test/test_gateway.py --persona hr-manager --list-tools
python test/test_gateway.py --persona employee --list-tools
python test/test_gateway.py --persona hr-specialist --query "Sarah Johnson"
```

### View CloudWatch logs

```bash
ENV=dev
aws logs tail /aws/lambda/hr-data-provider-lambda-${ENV} --since 1h --follow
aws logs tail /aws/lambda/hr-request-interceptor-lambda-${ENV} --since 1h --follow
aws logs tail /aws/lambda/hr-response-interceptor-lambda-${ENV} --since 1h --follow
```

## Troubleshooting

**Cedar `CREATE_FAILED: An internal error occurred during creation`**
Cedar's schema initialization failed — usually the engine is in a corrupted state from a prior failed run. Clean up and redeploy from Step 2:
```bash
bash scripts/cleanup.sh && bash scripts/prereq.sh --region us-east-1 --env dev
```

**Cedar `CREATE_FAILED: unable to find at offset 0`**
No Lambda target is registered. Complete Step 3 before running Step 4.
```bash
python scripts/agentcore_gateway.py create --config prerequisite/prereqs_config.yaml
```

**Runtime `CREATE_FAILED` — ARM64 binary incompatibility**
macOS packaging pulled darwin binaries. Delete the old zip and repackage:
```bash
rm -f dist/runtime.zip && bash scripts/package_runtime.sh
```

**SSM parameters missing when running the app**
Complete Steps 2–5 first. Verify all parameters are present:
```bash
aws ssm get-parameters-by-path --path /app/hrdlp --recursive --query "Parameters[].Name" --output text
```

**Runtime returns 403 after update**
`update-agent-runtime` resets fields not explicitly passed. Always run the full update:
```bash
python scripts/agentcore_agent_runtime.py update
```

## Project Structure

```
role-based-hr-data-agent/
├── agent_config/          # HRDataAgent — Strands + MCP/JSON-RPC
├── app_modules/           # Streamlit UI (auth, chat, persona selector)
├── docs/
│   ├── screenshots/       # Demo screenshots + full architecture diagram
│   └── diagrams/          # Per-persona request flow (flow.md)
├── scripts/               # Deployment CLI (gateway, runtime, Cedar, Cognito)
├── prerequisite/
│   ├── lambda/            # HR Data Provider + Request/Response Interceptors
│   ├── cedar/             # Cedar authorization policies
│   ├── infrastructure.yaml
│   └── cognito.yaml
├── test/                  # Gateway, agent, and field redaction tests
├── app.py                 # Streamlit entry point
├── main.py                # AgentCore Runtime entry point
└── requirements.txt
```

## Cleanup

```bash
bash scripts/cleanup.sh --region us-east-1 --env dev
```

> **Note (macOS / Windows):** After cleanup, the Cognito User Pool Domain (`hr-dlp-agent-*`) can take 30–60 seconds to fully de-register in AWS's DNS layer. If you immediately re-run `prereq.sh` and the Cognito stack fails with `Internal error reported from downstream service during operation 'CreateUserPoolDomain'`, wait 30 seconds and retry:
> ```bash
> aws cloudformation delete-stack --stack-name hr-dlp-cognito-dev
> aws cloudformation wait stack-delete-complete --stack-name hr-dlp-cognito-dev
> # wait 30 seconds, then:
> bash scripts/prereq.sh --region us-east-1 --env dev
> ```

## Contributing

We welcome contributions! See [Contributing Guidelines](../../CONTRIBUTING.md) for details.

## License

MIT License — see [LICENSE](../../LICENSE).

## Support

Report issues via [GitHub Issues](https://github.com/awslabs/agentcore-samples/issues).
