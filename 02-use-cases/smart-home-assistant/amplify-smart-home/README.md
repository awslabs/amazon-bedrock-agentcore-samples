# Smart Home Assistant UI Deployment Guide

A React web application that integrates with **[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** to provide an AI-powered smart home management interface.

> [!NOTE]
> **Working Directory**: Make sure you are in the `amplify-smart-home/` folder before starting this tutorial. All commands in this guide should be executed from this directory.

## Overview

A conversational AI assistant built with React that integrates with Amazon Bedrock AgentCore for smart home management.

**Services Deployed by This Guide:**
- **Amazon Cognito**: User authentication and authorization (via AWS Amplify)
- **AWS Amplify Hosting**: Web application hosting

**Pre-existing Resources Required:**
- **Amazon Bedrock AgentCore**: AI agent runtime
- **Amazon DynamoDB**: Media assets storage table

**How It Works:**
1. User authenticates via Amazon Cognito
2. User interacts with the AI assistant through conversational interface
3. Frontend sends queries to Amazon Bedrock AgentCore runtime
4. AgentCore processes requests and streams responses back in real-time
5. Media assets (videos, images) are retrieved from DynamoDB and displayed when relevant

> [!IMPORTANT]
> This sample application is for demonstration purposes only and is not production-ready. Please validate the code against your organization's security best practices.

## Prerequisites

- [Node.js 18+](https://nodejs.org/en/download/package-manager)
- Amazon Bedrock AgentCore runtime deployed
- DynamoDB table for session storage
- AWS CLI configured with appropriate permissions

## Installation

Install dependencies:

```bash
npm install
```

### Install Amplify CLI

Install the Amplify CLI globally:

``` bash
npm install -g @aws-amplify/cli
```

### Initialize Amplify Project

Initialize the Amplify project:

``` bash
amplify init
```

- Do you want to continue with Amplify Gen 1? **`yes`**
- Why would you like to use Amplify Gen 1? **`Prefer not to answer`**

Use the following configuration:

- ? Enter a name for the project: **`smarthomeassistant`**

Use the following default configuration:
- Name: **smarthomeassistant**
- Environment: dev
- Default editor: Visual Studio Code
- App type: javascript
- Javascript framework: react
- Source Directory Path: src
- Distribution Directory Path: build
- Build Command: npm run-script build
- Start Command: npm run-script start

- ? Initialize the project with the above configuration? **`Yes`**
- ? Select the authentication method you want to use: **`AWS profile`**

### Add Authentication

Add Amazon Cognito authentication to enable user sign-in:

``` bash
amplify add auth
```

Use the following configuration:

- Do you want to use the default authentication and security configuration?: **`Default configuration`**
- How do you want users to be able to sign in?: **`Email`**
- Do you want to configure advanced settings?: **`No, I am done`**

### Deploy Backend Resources

Deploy the authentication resources to AWS:

``` bash
amplify push
```

- ? Are you sure you want to continue? **`Yes`**

> [!NOTE]
> This creates a Cognito User Pool and Identity Pool in your AWS account for user authentication. AWS credentials for the Front-End Application are automatically managed through Cognito.

## Configure IAM Permissions

After deploying authentication, configure IAM permissions for your authenticated users:

1. **Find your AuthRole**: AWS Console → IAM → Roles → Search for `amplify-smarthomeassistant-dev-*-authRole`

2. **Add this inline policy** (replace placeholders with your actual values):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockAgentCore",
            "Effect": "Allow",
            "Action": "bedrock-agentcore:InvokeAgentRuntime",
            "Resource": [
                "<your-agent-runtime-arn>",
                "<your-agent-runtime-arn>/runtime-endpoint/*"
            ]
        },
        {
            "Sid": "DynamoDB",
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem"
            ],
            "Resource": "<your-dynamodb-table-arn>"
        }
    ]
}
```

**Required Resources:**
- **Agent Runtime ARN**: Your Amazon Bedrock AgentCore runtime ARN
- **DynamoDB Table ARN**: Your media assets storage table ARN

## Configuration

1. Copy the sample environment file:
   ```bash
   mv src/sample.env.js src/env.js
   ```

2. Update `src/env.js` with your AWS resources.

   Locate and update these sections marked with `// To Update`:

**Database Configuration** (around line 47):
```javascript
database: {
  tableName: "", // DynamoDB table for media assets - To Update
},
```

**Amazon Bedrock AgentCore Configuration** (around line 52):
```javascript
agent: {
  runtimeArn: "", // AgentCore runtime ARN - To Update
  endpointName: "DEFAULT", // Agent endpoint name - To Update
  //memoryTurns: 10, // Number of conversation turns to keep in memory
},
```

**Optional Customization:**
- `APP_NAME`: Application display name (default: "Smart Home")
- `assistantName`: Assistant display name
- `assistantDescription`: Description of assistant capabilities
- `sampleQuestions`: Array of sample questions for the welcome screen
  

## Usage

Start the development server:

```bash
npm start
```

The app opens at `http://localhost:3000` with AWS Amplify authentication.

**First-Time Access:**
1. Click "Create Account" and use your email
2. Check email for verification code
3. Sign in with your credentials

**Sample Queries:**
- "Find all people activities in videos"
- "Get statistics on detected object types"
- "Search for specific objects (couch, table, etc.)"
- "Show me recent security events"
- "What's the current status of all house systems?"

## Deployment

Deploy to AWS Amplify Hosting:

```bash
amplify add hosting
```

Configuration:
- Plugin module: **`Hosting with Amplify Console`**
- Type: **`Manual deployment`**

Publish:

```bash
amplify publish
```

Your application will be deployed and accessible via the provided URL.

## Application UI Previews

The Smart Home Assistant provides an intuitive conversational interface:

<table border="0">
<tr>
<td width="50%" valign="top">

### Welcome Assistant

![Smart Home Assistant Interface](../images/preview1.png)

*The Smart Home Assistant interface showing the conversational AI powered by Amazon Bedrock AgentCore.*

</td>
<td width="50%" valign="top">

### Media Assets Display

![Media Assets Display](../images/preview2.png)

*Real-time display of security camera videos and images with AI-powered analysis and object detection.*

</td>
</tr>
</table>

## License

This project is licensed under the Apache-2.0 License.

## Thanks

Thank you for following this guide! We hope this helps you build amazing AI-powered agent experiences.