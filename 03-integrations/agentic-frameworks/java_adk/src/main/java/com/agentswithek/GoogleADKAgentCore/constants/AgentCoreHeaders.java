package com.agentswithek.GoogleADKAgentCore.constants;

/**
 * Constants for Amazon Bedrock AgentCore Runtime HTTP headers.
 *
 * These headers are provided by the AgentCore Runtime and can be used
 * for tracking, authentication, and maintaining session context.
 */
public final class AgentCoreHeaders {

    private AgentCoreHeaders() {
        // Private constructor to prevent instantiation
        throw new UnsupportedOperationException("This is a utility class and cannot be instantiated");
    }

    /**
     * Session ID header provided by AgentCore Runtime.
     * Used to maintain conversation context across multiple invocations.
     */
    public static final String SESSION_ID_HEADER = "x-amzn-bedrock-agentcore-runtime-session-id";

    /**
     * Request ID header provided by AgentCore Runtime.
     * Used for tracking and debugging individual requests.
     */
    public static final String REQUEST_ID_HEADER = "x-amzn-requestid";

    /**
     * Workload access token header provided by AgentCore Runtime.
     * Used for authentication and authorization.
     */
    public static final String ACCESS_TOKEN_HEADER = "x-amzn-bedrock-agentcore-runtime-workload-accesstoken";
}
