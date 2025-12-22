# CopilotKit <> strands Starter

This is a starter template for building AI agents using [strands](https://strands.com) and [CopilotKit](https://copilotkit.ai). It provides a modern Next.js application with an integrated investment analyst agent that can research stocks, analyze market data, and provide investment insights.

## Prerequisites

- Node.js 20+ 
- Python 3.12+
- OpenAI API Key (for the strands agent)
- Any of the following package managers:
  - pnpm (recommended)
  - npm
  - yarn
  - bun

> **Note:** This repository ignores lock files (package-lock.json, yarn.lock, pnpm-lock.yaml, bun.lockb) to avoid conflicts between different package managers. Each developer should generate their own lock file using their preferred package manager. After that, make sure to delete it from the .gitignore.

## Getting Started

1. Install dependencies using your preferred package manager:
```bash
# Using pnpm (recommended)
pnpm install

# Using npm
npm install

# Using yarn
yarn install

# Using bun
bun install
```

> **Note:** Installing the package dependencies will also install the agent's python dependencies via the `install:agent` script.

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

or create a `.env` file.

```bash
echo "OPENAI_API_KEY=your-openai-api-key-here" > agent/.env
```

3. Start the development server:
```bash
# Using pnpm
pnpm dev

# Using npm
npm run dev

# Using yarn
yarn dev

# Using bun
bun run dev
```

This will start both the UI and agent servers concurrently.

## Available Scripts
The following scripts can also be run using your preferred package manager:
- `dev` - Starts both UI and agent servers in development mode
- `dev:debug` - Starts development servers with debug logging enabled
- `dev:ui` - Starts only the Next.js UI server
- `dev:agent` - Starts only the strands agent server
- `build` - Builds the Next.js application for production
- `start` - Starts the production server
- `lint` - Runs ESLint for code linting
- `install:agent` - Installs Python dependencies for the agent

## 📚 Documentation

The main UI component is in `src/app/page.tsx`. You can:
- Modify the theme colors and styling
- Add new frontend actions
- Customize the CopilotKit sidebar appearance

Otherwise, check out the documentation relevant to your task:

- [Strands Documentation](https://strandsagents.com/latest/documentation/docs/) - Learn more about Strands and its features
- [CopilotKit Documentation](https://docs.copilotkit.ai) - Explore CopilotKit's capabilities
- [Next.js Documentation](https://nextjs.org/docs) - Learn about Next.js features and API

## Contributing

Feel free to submit issues and enhancement requests! This starter is designed to be easily extensible.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### Agent Connection Issues
If you see "I'm having trouble connecting to my tools", make sure:
1. The strands agent is running on port 8000
2. Your OpenAI API key is set correctly
3. Both servers started successfully

### Python Dependencies
If you encounter Python import errors:
```bash
cd agent
uv sync
```







## Additional steps
...
Enable model access, deploy in US
AgentCore CLI



Set the AWS region
AWS_REGION="us-west-2"

...

# 1. Create User Pool

export USER_POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "AgentCoreAgUiPool" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region ${AWS_REGION} \
  --query 'UserPool.Id' --output text)
export DISCOVERY_URL="https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration"

# 2. Create App Client and set CLIENT_ID
export CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id ${USER_POOL_ID} \
  --client-name "AgentCoreAgUiPoolClient" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --region ${AWS_REGION} \
  --query 'UserPoolClient.ClientId' --output text)

# 3. Create User (replace USER_POOL_ID)
aws cognito-idp admin-create-user \
  --user-pool-id ${USER_POOL_ID} \
  --username "testuser" \
  --temporary-password "Temp1234" \
  --message-action "SUPPRESS" \
  --region ${AWS_REGION}

# 4. Set Permanent Password (replace USER_POOL_ID)
aws cognito-idp admin-set-user-password \
  --user-pool-id ${USER_POOL_ID} \
  --username "testuser" \
  --password "MyPassword123" \
  --permanent \
  --region ${AWS_REGION}

# 5. Authenticate and get tokens (replace CLIENT_ID)
export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id ${CLIENT_ID} \
  --auth-flow "USER_AUTH" \
  --auth-parameters "USERNAME=testuser,PASSWORD=MyPassword123, SECRET_HASH=gSUfqO3PCHbC7mABj5eh6gT6BOGmdr1Ii+W2+e/mvDQ=" \
  --region ${AWS_REGION} | jq -r '.AuthenticationResult.AccessToken')

echo -n "testuser384u6og70fhln7hgu6ogefa7mi" | openssl dgst -sha256 -hmac an5mbj95b46sc94l4pjglbpptluv9ft7v4q3hrqbdc4n899d779 -binary | openssl enc -base64

cd agent
agentcore configure -e main.py --name ag_ui_agent --requirements-file pyproject.toml --deployment-type container --disable-memory --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$CLIENT_ID\"]}}" --non-interactive --region ${AWS_REGION}
agentcore launch


export STRANDS_AGENT_URL="https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-west-2%3A536253303170%3Aruntime%2Fag_ui_agent-Z2gtJJ7cmm/invocations?qualifier=DEFAULT"


npm install
npm dev:ui

export BEDROCK_AGENT_CORE_ENDPOINT_URL="https://bedrock-agentcore.us-west-2.amazonaws.com"
export ESCAPED_AGENT_ARN="arn%3Aaws%3Abedrock-agentcore%3Aus-west-2%3A536253303170%3Aruntime%2Fag_ui_agent-Z2gtJJ7cmm"
curl -v -X POST "${BEDROCK_AGENT_CORE_ENDPOINT_URL}/runtimes/${ESCAPED_AGENT_ARN}/invocations?qualifier=DEFAULT" \
-H "Authorization: Bearer ${TOKEN}" \
-H "X-Amzn-Trace-Id: your-trace-id" \
-H "Content-Type: application/json" \
-H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: 1234567890123456789012345678901234567890" \
-d @test_input.json
