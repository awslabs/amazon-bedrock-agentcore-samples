package com.agentswithek.GoogleADKAgentCore.controllers;

import com.agentswithek.GoogleADKAgentCore.agent.GoogleADKAgent;
import com.agentswithek.GoogleADKAgentCore.constants.AgentCoreHeaders;
import com.agentswithek.GoogleADKAgentCore.entities.InvocationRequest;
import com.agentswithek.GoogleADKAgentCore.entities.InvocationResponse;
import com.agentswithek.GoogleADKAgentCore.entities.PingResponse;
import com.google.adk.agents.RunConfig;
import com.google.adk.events.Event;
import com.google.adk.runner.InMemoryRunner;
import com.google.adk.sessions.Session;
import com.google.genai.types.Content;
import com.google.genai.types.Part;
import io.reactivex.rxjava3.core.Flowable;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * REST Controller implementing the HTTP protocol contract for Amazon Bedrock AgentCore Runtime.
 *
 * Required endpoints:
 * - POST /invocations: Main agent interaction endpoint
 * - GET /ping: Health check endpoint
 */
@RestController
public class AgentCoreRuntimeController {

    // Initialize Google ADK runner
    private final InMemoryRunner runner = new InMemoryRunner(GoogleADKAgent.ROOT_AGENT);
    private final RunConfig runConfig = RunConfig.builder().build();

    // Session cache to maintain conversation context
    private final ConcurrentHashMap<String, Session> sessionCache = new ConcurrentHashMap<>();

    /**
     * POST /invocations - Main agent interaction endpoint.
     *
     * Receives incoming requests with a prompt and processes them through Google ADK agent.
     *
     * @param request The invocation request containing the prompt
     * @param sessionId The session ID from Amazon Bedrock AgentCore Runtime (required)
     * @param requestId The request ID from Amazon Bedrock AgentCore Runtime (optional)
     * @param accessToken The workload access token from Amazon Bedrock AgentCore Runtime (optional)
     * @return Agent response with message and timestamp
     */
    @PostMapping("/invocations")
    public ResponseEntity<InvocationResponse> invocations(
            @Valid @RequestBody InvocationRequest request,
            @RequestHeader(AgentCoreHeaders.SESSION_ID_HEADER) String sessionId,
            @RequestHeader(value = AgentCoreHeaders.REQUEST_ID_HEADER, required = false) String requestId,
            @RequestHeader(value = AgentCoreHeaders.ACCESS_TOKEN_HEADER, required = false) String accessToken) {

        // Log the headers
        System.out.println("Received request - Session ID: " + sessionId);
        if (requestId != null) {
            System.out.println("Request ID: " + requestId);
        }
        if (accessToken != null) {
            System.out.println("Access Token: [REDACTED]");
        }

        try {
            // Get or create session for this sessionId
            Session session = sessionCache.computeIfAbsent(sessionId, sid -> {
                System.out.println("Creating new Google ADK session for: " + sid);
                return runner.sessionService()
                    .createSession(runner.appName(), "user-" + sid)
                    .blockingGet();
            });

            // Create user message content
            Content userMsg = Content.fromParts(Part.fromText(request.getPrompt()));

            // Run agent and collect response
            Flowable<Event> events = runner.runAsync(session.userId(), session.id(), userMsg, runConfig);

            List<String> responses = new ArrayList<>();
            events.blockingForEach(event -> {
                if (event.finalResponse()) {
                    responses.add(event.stringifyContent());
                }
            });

            // Combine all responses
            String agentResponse = String.join("\n", responses);
            System.out.println("Agent response: " + agentResponse);

            return ResponseEntity.ok(InvocationResponse.of(agentResponse));

        } catch (Exception e) {
            System.err.println("Error processing request: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.ok(InvocationResponse.of(
                "Error processing request: " + e.getMessage()
            ));
        }
    }

    /**
     * GET /ping - Health check endpoint.
     *
     * Verifies that the agent is operational and ready to handle requests.
     * Returns status: "healthy" or "healthyBusy" with Unix timestamp.
     *
     * @return Health status response
     */
    @GetMapping("/ping")
    public ResponseEntity<PingResponse> ping() {
        return ResponseEntity.ok(PingResponse.healthy());
    }
}