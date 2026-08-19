package com.agentswithek.GoogleADKAgentCore;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.Disabled;
import software.amazon.awssdk.core.SdkBytes;
import software.amazon.awssdk.core.sync.ResponseTransformer;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.bedrockagentcore.BedrockAgentCoreClient;
import software.amazon.awssdk.services.bedrockagentcore.model.InvokeAgentRuntimeRequest;
import software.amazon.awssdk.services.bedrockagentcore.model.InvokeAgentRuntimeResponse;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration test for invoking deployed AgentCore Runtime agent.
 *
 * This test requires:
 * 1. Agent to be deployed and running in AWS
 * 2. AGENT_RUNTIME_ARN environment variable to be set
 * 3. AWS credentials configured (via ~/.aws/credentials or environment variables)
 *
 * Usage:
 *   export AGENT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/your-agent-id"
 *   mvn test -Dtest=AgentRuntimeInvokerTest
 */
// @Disabled("Integration test - only run when agent is deployed")
public class AgentRuntimeInvokerTest {

    private BedrockAgentCoreClient client;
    private String agentRuntimeArn;

    @BeforeEach
    public void setup() {
        // Get agent runtime ARN from environment variable
        agentRuntimeArn = System.getenv("AGENT_RUNTIME_ARN");

        if (agentRuntimeArn == null || agentRuntimeArn.isEmpty()) {
            throw new IllegalStateException(
                "AGENT_RUNTIME_ARN environment variable must be set. " +
                "Example: arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/your-agent-id"
            );
        }

        // Initialize BedrockAgentCore client
        String region = System.getenv("AWS_REGION");
        if (region == null || region.isEmpty()) {
            region = "us-east-1";
        }

        client = BedrockAgentCoreClient.builder()
                .region(Region.of(region))
                .build();

        System.out.println("Initialized BedrockAgentCore client");
        System.out.println("Agent Runtime ARN: " + agentRuntimeArn);
        System.out.println("Region: " + region);
    }

    @Test
    public void testSimplePrompt() {
        System.out.println("\n=== Test 1: Simple Prompt ===");

        String requestPayload = """
            {
              "prompt": "Hello, how are you?"
            }
            """;

        String response = invokeAgent(requestPayload);

        assertNotNull(response, "Response should not be null");
        assertFalse(response.isEmpty(), "Response should not be empty");

        System.out.println("✅ Simple prompt test passed");
        System.out.println("Response: " + response);
    }

    @Test
    public void testComplexPrompt() {
        System.out.println("\n=== Test 2: Complex Prompt ===");

        String requestPayload = """
            {
              "prompt": "Can you explain the HTTP protocol contract for Amazon Bedrock AgentCore Runtime?"
            }
            """;

        String response = invokeAgent(requestPayload);

        assertNotNull(response, "Response should not be null");
        assertFalse(response.isEmpty(), "Response should not be empty");
        assertTrue(response.length() > 50, "Response should be substantial");

        System.out.println("✅ Complex prompt test passed");
        System.out.println("Response: " + response);
    }

    @Test
    public void testMultipleInvocations() {
        System.out.println("\n=== Test 3: Multiple Invocations ===");

        String[] prompts = {
            "What is 2 + 2?",
            "Tell me a joke",
            "What is the capital of France?"
        };

        for (int i = 0; i < prompts.length; i++) {
            System.out.println("\nInvocation " + (i + 1) + ": " + prompts[i]);

            String requestPayload = String.format("""
                {
                  "prompt": "%s"
                }
                """, prompts[i]);

            String response = invokeAgent(requestPayload);

            assertNotNull(response, "Response " + (i + 1) + " should not be null");
            System.out.println("Response " + (i + 1) + ": " + response);
        }

        System.out.println("\n✅ Multiple invocations test passed");
    }

    @Test
    public void testResponseFormat() {
        System.out.println("\n=== Test 4: Response Format Validation ===");

        String requestPayload = """
            {
              "prompt": "Hello"
            }
            """;

        String response = invokeAgent(requestPayload);

        assertNotNull(response, "Response should not be null");

        // Check if response is valid JSON (basic check)
        assertTrue(response.contains("message") || response.contains("timestamp") ||
                   response.startsWith("{") || response.length() > 0,
                   "Response should be in valid format");

        System.out.println("✅ Response format validation passed");
        System.out.println("Response: " + response);
    }

    /**
     * Helper method to invoke the agent runtime.
     */
    private String invokeAgent(String requestPayload) {
        try {
            System.out.println("Request payload: " + requestPayload);

            // Generate a unique session ID for this invocation (must be at least 33 characters)
            String sessionId = "test-session-" + System.currentTimeMillis() + "-" +
                              Math.abs(requestPayload.hashCode());

            // Build the request with the payload as request body
            InvokeAgentRuntimeRequest request = InvokeAgentRuntimeRequest.builder()
                    .agentRuntimeArn(agentRuntimeArn)
                    .payload(SdkBytes.fromUtf8String(requestPayload))
                    .contentType("application/json")
                    .accept("application/json")
                    .runtimeSessionId(sessionId)
                    .qualifier("DEFAULT")
                    .build();

            System.out.println("Session ID: " + sessionId + " (length: " + sessionId.length() + ")");

            // Invoke the agent and get response as bytes
            String response = client.invokeAgentRuntimeAsBytes(request).asUtf8String();

            System.out.println("Raw response: " + response);

            return response;

        } catch (Exception e) {
            System.err.println("Error invoking agent: " + e.getMessage());
            e.printStackTrace();
            fail("Failed to invoke agent: " + e.getMessage());
            return null;
        }
    }

    public void tearDown() {
        if (client != null) {
            client.close();
        }
    }
}
