# Auth Code Flow with MCP Targets - [URL Mode Elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation#url-mode-flow)

Introductory Blog: [Connecting MCP servers to Amazon Bedrock AgentCore gateway using Authorization Code flow](https://aws.amazon.com/blogs/machine-learning/connecting-mcp-servers-to-amazon-bedrock-agentcore-gateway-using-authorization-code-flow/)

To provide support for Authorization Code Grant type, we provide two ways for target creations.

1. Implicit sync during MCP Server target creation

   In this method, the admin user completes the authorization code flow during [CreateGatewayTarget](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateGatewayTarget.html), [UpdateGatewayTarget](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateGatewayTarget.html), or [SynchronizeGatewayTargets](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_SynchronizeGatewayTargets.html) operations, allowing AgentCore gateway to discover and cache the MCP server's tools upfront.

2. Provide schema upfront during MCP Server targets creating

   With this method, admin users provide the tool schema directly during [CreateGatewayTarget](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateGatewayTarget.html) or [UpdateGatewayTarget](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateGatewayTarget.html) operations, rather than AgentCore gateway fetching them dynamically from the MCP server. AgentCore gateway parses the provided schema and caches the tool definitions. This eliminates the need for the admin user to complete the authorization code flow during target creation or update. This is the recommended approach when human intervention is not possible during create/update operations, such as when using a Infrastructure-as-code pipeline to manage AgentCore gateway resources. Also, this method is beneficial when you do not want to expose all the tools provided by the MCP server target, i.e. you only expose the tools you require in the tool schema.


   Note: Since tool schemas are provided upfront with this method, the [SynchronizeGatewayTargets](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_SynchronizeGatewayTargets.html) operation is not supported. You can switch a target between Method 1 and Method 2 by updating the target configuration.

This means AgentCore gateway users will be able to call `list/tools` without being prompted to authenticate with the MCP server authentication server, as this fetches the cached tools. The authorization code flow is only triggered when a gateway user invokes a tool on that MCP server. This is particularly beneficial when multiple MCP servers are attached to a single gateway — users can browse the full tool catalog (cached tools) without authenticating to every MCP server and only complete the flow for the specific server whose tool they invoke.

## URL Session Binding

[URL Session Binding](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/oauth2-authorization-url-session-binding.html) ensures that the user who initiated the OAuth authorization request is the same user who granted consent. When AgentCore identity generates an authorization URL, it also returns a session-URI. After the user completes consent, the browser redirects back to a callback URL with the session-URI. The application then is responsible for calling the [CompleteResourceTokenAuth](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CompleteResourceTokenAuth.html) API, presenting both the user's identity and the session-URI. AgentCore identity validates that the user who started the flow is the same user who completed it before exchanging the authorization code for an access token. This prevents a scenario where a user accidentally shares the authorization URL, and someone else completes the consent, which would grant access tokens to the wrong party. The authorization URL and session URI are only valid for 10 minutes, further limiting the window for misuse. Session binding applies during admin target creation (implicit sync) and during tool invocation.

### Implicit sync during MCP Server target creation

In this section, we will introduce how implicit sync during MCP Server target creation works. Make sure that the AgentCore gateway execution role has `GetWorkloadAccessTokenForUserId` and `CompleteResourceTokenAuth` permissions. First, let's start by understanding the flow.

![implicit](./images/implicit.png)

1. The admin user calls `CreateGatewayTarget`, providing the MCP server endpoint, the AgentCore identity Credential Provider, and return URL. This tells AgentCore gateway which MCP server to connect to and which credential provider to use for obtaining OAuth 2.0 tokens. This same flow also applies to `UpdateGatewayTarget` and `SynchronizeGatewayTargets` operations.

2. AgentCore gateway requests a workload access token from the AgentCore identity Credential Provider, passing the AgentCore gateway workload identity and a user ID in the format `{gatewayId}{targetId}{uuid}`. This workload access token identifies the AgentCore gateway as an authorized caller for subsequent credential operations.

3. Using the workload access token, AgentCore gateway requests an OAuth 2.0 access token from the AgentCore identity Credential Provider. This provides the admin user with an authorization URL and a session-URI. At this stage, the target is in `Needs Authorization` status.  

4. The admin opens the authorization URL in their browser, signs in, and grants the requested permissions to the AgentCore gateway.

5. After the admin grants consent, the OAuth 2.0 authorization server sends an authorization code to the AgentCore identity Credential Provider's registered callback endpoint.

6. The credential provider redirects the admin browser to the return URL, with the session URI. The admin application calls `CompleteResourceTokenAuth`, presenting the user id and the session-URI returned in step 2. The credential provider validates that the user who initiated the authorization flow (step 3) is the same user who completed consent. This revents token hijacking if the authorization URL was accidentally shared. If the flow was initiated from the AWS Console, this step is handled automatically. If initiated from another context, the admin is responsible for calling the `CompleteResourceTokenAuth` API directly.

7. After successful session binding validation, the credential provider exchanges the authorization code with the OAuth 2.0 authorization server for an OAuth 2.0 access token.

8. This access token is used to list the tools on MCP server target; returned tool definitions from the target are cached at AgentCore gateway.

### Provide schema upfront during MCP Server targets creation 

In this section, we introduce how to provide the schema upfront during MCP Server targets creation. This is the recommended approach when human intervention isn’t possible during create/update operations.

![schema](./images/schema-upfront.png)

In this step, we create an Amazon Bedrock AgentCore gateway and Target and provide schema upfront during the MCP Server targets creation. The process remains the same. During target creation selection, select `Use pre-defined list tools` and paste the GitHub tools definitions.

### Security Considerations

- **Credential Handling**: OAuth client secrets are collected via `getpass` and stored only in memory during notebook execution. For production, store secrets in AWS Secrets Manager and retrieve them programmatically.
- **Least Privilege IAM**: The AWS Identity and Access Management (IAM) role created in this notebook follows least-privilege principles with scoped-down policies for specific AgentCore resources.
- **Token Expiry**: Access tokens and authorization URLs expire after a limited time (typically 1 hour for tokens, 10 minutes for authorization URLs). Expired tokens are automatically refreshed by AgentCore identity when refresh tokens are available.
- **Logging**: For production deployments, enable AWS CloudTrail to log all AgentCore API calls and configure Amazon CloudWatch for monitoring gateway invocations.
- **Shared Responsibility**: AWS manages the AgentCore gateway infrastructure and AgentCore identity service. Customers are responsible for securing their OAuth app credentials, configuring appropriate IAM policies, and implementing secure callback endpoints for session binding.

## Samples

| Sample | MCP Server | Description |
| :--- | :--- | :--- |
| [GitHub](github/) | [GitHub Copilot MCP](https://api.githubcopilot.com/mcp) | Connect GitHub MCP Server with authorization code flow, implicit sync and schema-upfront methods |
