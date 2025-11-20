package com.agentswithek.GoogleADKAgentCore.entities;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * Request entity for /invocations endpoint.
 * Follows the HTTP protocol contract for Amazon Bedrock AgentCore Runtime.
 */
@AllArgsConstructor
@NoArgsConstructor
@Getter
@Setter
public class InvocationRequest {

    @NotBlank(message = "Prompt is required")
    private String prompt;
}
