package com.agentswithek.GoogleADKAgentCore.agent;

import com.google.adk.agents.BaseAgent;
import com.google.adk.agents.LlmAgent;
import com.google.adk.tools.Annotations.Schema;
import com.google.adk.tools.FunctionTool;

import java.util.Map;

public class GoogleADKAgent {
    public static BaseAgent ROOT_AGENT = initAgent();

    private static BaseAgent initAgent() {
        return LlmAgent.builder()
            .name("hello-time-agent")
            .description("Tells the current time in a specified city")
            .instruction("""
                You are a helpful assistant that tells the current time in a city.
                Use the 'getCurrentTime' tool for this purpose.
                """)
            .model("gemini-2.5-flash")
            .tools(FunctionTool.create(GoogleADKAgent.class, "getCurrentTime"))
            .build();
    }

    /** Mock tool implementation */
    @Schema(description = "Get the current time for a given city")
    public static Map<String, String> getCurrentTime(
        @Schema(name = "city", description = "Name of the city to get the time for") String city) {
        return Map.of(
            "city", city,
            "forecast", "The time is 10:30am."
        );
    }
}
