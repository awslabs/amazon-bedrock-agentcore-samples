package com.agentswithek.GoogleADKAgentCore.entities;

import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * Response entity for /ping endpoint.
 * Follows the HTTP protocol contract for Amazon Bedrock AgentCore Runtime.
 */
@AllArgsConstructor
@Getter
public class PingResponse {

    private String status;
    private Long timeOfLastUpdate;

    /**
     * Creates a healthy status response with current timestamp.
     */
    public static PingResponse healthy() {
        return new PingResponse("healthy", System.currentTimeMillis() / 1000);
    }

    /**
     * Creates a healthy but busy status response with current timestamp.
     */
    public static PingResponse healthyBusy() {
        return new PingResponse("healthyBusy", System.currentTimeMillis() / 1000);
    }
}
