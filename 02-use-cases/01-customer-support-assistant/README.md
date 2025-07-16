# Customer Support Agent

> [!CAUTION]
> The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments. Make sure to have Amazon Bedrock Guardrails in place to protect against [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).

This is a customer support agent implementation using AWS Bedrock AgentCore framework. The system provides an AI-powered customer support interface with capabilities for warranty checking, customer profile management, Google calendar integration, and Amazon Bedrock Knowledge Base retrieval.

![architecture](./images/architecture.png)

## Prerequisites

### AWS Account Setup

1. **AWS Account**: You need an active AWS account with appropriate permissions
   - [Create AWS Account](https://aws.amazon.com/account/)
   - [AWS Console Access](https://aws.amazon.com/console/)

2. **AWS CLI**: Install and configure AWS CLI with your credentials
   - [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [Configure AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

   ```bash
   aws configure
   ```

3. **Bedrock Model Access**: Enable access to Amazon Bedrock Anthropic Claude 4.0 models in your AWS region
   - Navigate to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/)
   - Go to "Model access" and request access to:
     - Anthropic Claude Sonnet models
   - [Bedrock Model Access Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. **Python 3.8+**: Required for running the application
   - [Python Downloads](https://www.python.org/downloads/)

5. **Create OAuth 2.0 credentials for calendar access** : For Google Calendar integration
   - Follow [Google OAuth Setup](./prerequisite/google_oauth_setup.md)

6. **Install [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager**.

## Deploy

1. Create infrastructure

    ```bash
    python -m venv .venv
    source .venv/bin/activate

    chmod +x scripts/prereq.sh
    ./scripts/prereq.sh

    chmod +x scripts/list_ssm_parameters.sh
    ./scripts/list_ssm_parameters.sh
    ```

2. Create Agentcore Gateway

    ```bash
    python scripts/agentcore_gateway.py create --name customersupgateway
    ```

    This create `gateway.config` file.

3. Setup Agentcore Identity

    - Setup Cognito Credential Provider

    ```bash
    python scripts/cognito_credentials_provider.py create --name customersupport-gateways

    python test/test_gateway.py --prompt "Check warranty with serial number MNO33333333"
    ```

    - Setup Google Credential Provider

    Follow instructions to setup [Google Credentials](./prerequisite/google_oauth_setup.md).

    ```bash
    python scripts/google_credentials_provider.py create --name customersupport-google-calendar

    python test/test_google_tool.py
    ```

4. Create Memory

    ```bash
    python scripts/agentcore_memory.py create --name customersupport

    ```

5. Setup Agent Runtime

    ```bash

    agentcore configure --entrypoint main.py -er arn:aws:iam::<Account-Id>:role/<Role> --name customersupport<AgentName>
    ```

    Use `./scripts/list_ssm_parameters.sh` to fill:
    - `Role = ValueOf(/app/customersupport/agentcore/agentcore_iam_role)`
    - `Oath Discovery URL = ValueOf(/app/customersupport/agentcore/cognito_discovery_url)`
    - `Oath client id = ValueOf(/app/customersupport/agentcore/web_client_id)`.

    ![configure](./images/runtime_configure.png)

    ```bash
    agentcore launch

    python test/test_agent.py customersupport<AgentName> -p "Hi"
    ```

6. Local Host Streamlit UI

```bash
pip install streamlit
streamlit run app.py -- --agent=customersupport<AgentName>
```

## Scripts

### Amazon Bedrock AgentCore Gateway

#### Create Amazon Bedrock AgentCore Gateway

```bash
python scripts/agentcore_gateway.py create --name my-gateway
python scripts/agentcore_gateway.py create --name my-gateway --api-spec-file custom/path.json
```

#### Delete Amazon Bedrock AgentCore Gateway

```bash
# Delete gateway (reads from gateway.config automatically)
python scripts/agentcore_gateway.py delete

# Delete with confirmation skip
python scripts/agentcore_gateway.py delete --confirm
```

### Amazon Bedrock AgentCore Memory

#### Create Amazon Bedrock AgentCore Memory

```bash
python scripts/agentcore_memory.py create --name MyMemory
python scripts/agentcore_memory.py create --name MyMemory --event-expiry-days 60
```

#### Delete Amazon Bedrock AgentCore Memory

```bash
# Delete memory (reads from SSM automatically)
python scripts/agentcore_memory.py delete

# Delete with confirmation skip
python scripts/agentcore_memory.py delete --confirm
```

### Cognito Credentials Provider

#### Create Cognito Credentials Provider

```bash
python scripts/cognito_credentials_provider.py create --name customersupport-gateways
```

#### Delete Cognito Credentials Provider

```bash
# Delete provider (reads name from SSM automatically)
python scripts/cognito_credentials_provider.py delete

# Delete specific provider by name
python scripts/cognito_credentials_provider.py delete --name customersupport-gateways

# Delete with confirmation skip
python scripts/cognito_credentials_provider.py delete --confirm
```

### Google Credentials Provider

#### Create Credentials Provider

```bash
python scripts/google_credentials_provider.py create --name customersupport-google-calendar
python scripts/google_credentials_provider.py create --name my-provider --credentials-file /path/to/credentials.json
```

#### Delete Credentials Provider

```bash
# Delete provider (reads name from SSM automatically)
python scripts/google_credentials_provider.py delete

# Delete specific provider by name
python scripts/google_credentials_provider.py delete --name customersupport-google-calendar

# Delete with confirmation skip
python scripts/google_credentials_provider.py delete --confirm
```

## Cleanup

```bash
chmod +x scripts/cleanup.sh
./scripts/cleanup.sh

python scripts/google_credentials_provider.py delete
python scripts/cognito_credentials_provider.py delete
python scripts/agentcore_memory.py delete
python scripts/agentcore_gateway.py delete
python scripts/agencore_agent_runtime.py delete
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](../../CONTRIBUTING.md) for details on:

- Adding new samples
- Improving existing examples
- Reporting issues
- Suggesting enhancements

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## 🆘 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues)
- **Documentation**: Check individual folder READMEs for specific guidance

## 🔄 Updates

This repository is actively maintained and updated with new capabilities and examples. Watch the repository to stay updated with the latest additions.
