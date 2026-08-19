import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from "@aws-sdk/client-bedrock-agentcore";
import * as crypto from "crypto";
import { SSMClient, GetParameterCommand } from "@aws-sdk/client-ssm";

/**
 * Script to invoke the Bedrock AgentCore Runtime
 *
 * Usage:
 *   npm run invoke-agent
 *
 * Environment variables:
 *   AWS_REGION - AWS region (default: us-east-1)
 *   AGENT_NAME - Agent name to retrieve ARN from SSM (required)
 *   PROMPT - The prompt to send to the agent (default: "Hello, how are you?")
 */

async function getAgentRuntimeArn(agentName: string, region: string): Promise<string> {
  const ssmClient = new SSMClient({ region });

  const parameterName = `/hostagent/agentcore/${agentName}/runtime-arn`;

  console.log(`🔍 Retrieving agent runtime ARN from SSM parameter: ${parameterName}`);

  try {
    const command = new GetParameterCommand({
      Name: parameterName,
      WithDecryption: false
    });

    const response = await ssmClient.send(command);

    if (!response.Parameter?.Value) {
      throw new Error(`Parameter ${parameterName} not found or has no value`);
    }

    console.log(`✅ Retrieved ARN: ${response.Parameter.Value}`);
    return response.Parameter.Value;
  } catch (error) {
    console.error('❌ Failed to retrieve parameter:', parameterName, error);
    throw error;
  }
}

async function invokeAgentRuntime(
  agentRuntimeArn: string,
  prompt: string,
  region: string
): Promise<void> {
  const client = new BedrockAgentCoreClient({ region });

  // Generate a unique session ID for this invocation (minimum 33 characters)
  const timestamp = Date.now();
  // Generate cryptographically secure random part (26 base36 chars from 16 bytes)
  const randomPart = crypto.randomBytes(16).toString("base36");
  const runtimeSessionId = `session-${timestamp}-${randomPart}`;

  console.log(`\n📤 Invoking agent runtime...`);
  console.log(`   ARN: ${agentRuntimeArn}`);
  console.log(`   Session ID: ${runtimeSessionId}`);
  console.log(`   Prompt: "${prompt}"\n`);

  // Convert prompt to Uint8Array payload
  const payload = new TextEncoder().encode(JSON.stringify({
    prompt: prompt
  }));

  const input = {
    agentRuntimeArn: agentRuntimeArn,
    payload: payload,
    contentType: "application/json",
    accept: "application/json",
    runtimeSessionId: runtimeSessionId,
    qualifier: "DEFAULT"
  };

  try {
    const command = new InvokeAgentRuntimeCommand(input);
    const response = await client.send(command);

    console.log(`✅ Agent runtime invoked successfully!`);
    console.log(`   Status Code: ${response.statusCode}`);
    console.log(`   Content Type: ${response.contentType}`);
    console.log(`   Runtime Session ID: ${response.runtimeSessionId}`);

    if (response.traceId) {
      console.log(`   Trace ID: ${response.traceId}`);
    }

    // Stream the response as chunks arrive
    if (response.response) {
      console.log(`\n📥 Streaming response from agent:\n`);

      let fullResponse = '';

      // The AWS SDK response is a StreamingBlobPayloadOutputTypes
      // We need to handle it as a Node.js Readable stream
      const stream = response.response as any;

      // Check if stream has the transformToWebStream method (AWS SDK v3 pattern)
      if (typeof stream.transformToWebStream === 'function') {
        const webStream = stream.transformToWebStream();
        const reader = webStream.getReader();
        const decoder = new TextDecoder();

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value, { stream: true });
            process.stdout.write(text);
            fullResponse += text;
          }
        } finally {
          reader.releaseLock();
        }
      } else {
        // Fallback to transformToString if streaming not available
        fullResponse = await response.response.transformToString();
        console.log(fullResponse);
      }

      console.log('\n'); // New line after streaming

      // Try to parse as JSON for prettier output
      try {
        const jsonResponse = JSON.parse(fullResponse);
        console.log(`\n📋 Parsed response:`);
        console.log(JSON.stringify(jsonResponse, null, 2));
      } catch {
        // If not JSON, that's fine - already printed above
      }
    }
  } catch (error) {
    console.error(`❌ Failed to invoke agent runtime:`, error);
    throw error;
  }
}

async function main() {
  // Get configuration from environment variables
  const region = process.env.AWS_REGION || "us-east-1";
  const agentName = process.env.AGENT_NAME;
  const prompt = process.env.PROMPT || "Hello, how are you?";

  if (!agentName) {
    console.error(`❌ Error: AGENT_NAME environment variable is required`);
    console.error(`\nUsage: AGENT_NAME=<agent-name> npm run invoke-agent`);
    process.exit(1);
  }

  console.log(`🚀 Starting Agent Runtime Invocation`);
  console.log(`   Region: ${region}`);
  console.log(`   Agent Name: ${agentName}\n`);

  try {
    // Step 1: Retrieve agent runtime ARN from SSM
    const agentRuntimeArn = await getAgentRuntimeArn(agentName, region);

    // Step 2: Invoke the agent runtime
    await invokeAgentRuntime(agentRuntimeArn, prompt, region);

    console.log(`\n✅ Invocation completed successfully!`);
  } catch (error) {
    console.error(`\n❌ Invocation failed:`, error);
    process.exit(1);
  }
}

// Run the main function
main();
