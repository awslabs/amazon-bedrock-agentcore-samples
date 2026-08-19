package com.agentswithek.GoogleADKAgentCore.entities;

import lombok.AllArgsConstructor;
import lombok.Getter;
import java.time.Instant;

/**
 * Response entity for /invocations endpoint.
 * Follows the HTTP protocol contract for Amazon Bedrock AgentCore Runtime.
 */
@AllArgsConstructor
@Getter
public class InvocationResponse {

    private String message;
    private String timestamp;

    /**
     * Creates a response with the given message and current timestamp.
     */
    public static InvocationResponse of(String message) {
        return new InvocationResponse(message, Instant.now().toString());
    }
}
