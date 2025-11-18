import { v4 as uuidv4 } from "uuid";
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";
import { createAwsClient } from "./AwsAuth";
import { getQueryResults } from "./AwsCalls";
import { AGENT_RUNTIME_ARN, AGENT_ENDPOINT_NAME } from "../env";

export const getAnswer = async (
  my_query,
  sessionId,
  setControlAnswers,
  setAnswers,
  setEnabled,
  setLoading,
  setErrorMessage,
  setQuery,
  setCurrentWorkingToolId
) => {
  if (!setLoading || my_query === "") return;

  setControlAnswers((prevState) => [...prevState, {}]);
  setAnswers((prevState) => [...prevState, { query: my_query }]);
  setEnabled(false);
  setLoading(true);
  setErrorMessage("");
  setQuery("");

  try {
    const queryUuid = uuidv4();
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    let json = {
      text: [],
      queryUuid,
    };

    console.log("🆔 Query UUID:", queryUuid);

    // Add initial answer object to state
    setControlAnswers((prevState) => [
      ...prevState,
      { current_tab_view: "answer" },
    ]);
    setAnswers((prevState) => [...prevState, json]);

    // Create AWS client for Bedrock Agent Core
    const agentCore = await createAwsClient(BedrockAgentCoreClient);

    // Create the payload for the agent
    const payload = JSON.stringify({
      prompt: my_query,
      session_id: sessionId,
      prompt_uuid: queryUuid,
      user_timezone: timezone,
      last_k_turns: 10,
    });

    const input = {
      agentRuntimeArn: AGENT_RUNTIME_ARN,
      qualifier: AGENT_ENDPOINT_NAME,
      payload,
      runtimeSessionId: sessionId
    };

    console.log("📤 Agent Core Input:", input);

    // Invoke the agent runtime command
    const command = new InvokeAgentRuntimeCommand(input);
    const response = await agentCore.send(command);

    let responseText = "";
    let currentTextItem = "";
    let textArray = [];

    console.log("🤖 Agent Response (Streaming):");

    try {
      // Handle streaming response
      if (response.response) {
        const stream = response.response.transformToWebStream();
        const reader = stream.getReader();
        const decoder = new TextDecoder();

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            console.log("📦 Streaming Chunk:", chunk);

            // Check for Bedrock service errors in the raw chunk
            if (chunk.includes("serviceUnavailableException") ||
              chunk.includes("Bedrock is unable to process your request") ||
              chunk.includes("I apologize, but I encountered an error")) {
              console.error("🚨 Bedrock Service Error detected in chunk:", chunk);
              throw new Error("Bedrock service is currently unavailable. Please try again in a few moments.");
            }

            // Process streaming data - Extract data objects from AWS SDK format
            const dataObjects = [];
            let currentToolName = "";

            chunk.split("\n").forEach((line) => {
              if (line.trim() && line.startsWith("data: ")) {
                const jsonString = line.replace(/^data: /, '{"data": ') + "}";
                try {
                  const obj = JSON.parse(jsonString);

                  // Check for error messages in the raw data
                  if (obj.data && typeof obj.data === 'string') {
                    // Check for Bedrock service unavailable error
                    if (obj.data.includes("serviceUnavailableException") ||
                      obj.data.includes("Bedrock is unable to process your request") ||
                      obj.data.includes("I apologize, but I encountered an error")) {
                      console.error("🚨 Bedrock Service Error detected in stream:", obj.data);
                      throw new Error("Bedrock service is currently unavailable. Please try again in a few moments.");
                    }
                  }

                  const data_object = JSON.parse(obj.data);
                  dataObjects.push(data_object);
                } catch (error) {
                  // If it's our custom error, re-throw it
                  if (error.message.includes("Bedrock service is currently unavailable")) {
                    throw error;
                  }
                  console.error("Error parsing JSON:", error);
                }
              }
            });

            // Process each data object with event handling logic
            for (const jsonData of dataObjects) {
              try {
                // Handle different event types
                if (jsonData.event?.contentBlockStart?.start?.toolUse) {
                  // Add accumulated text before tool block
                  if (currentTextItem.trim()) {
                    textArray.push({ type: "text", content: currentTextItem });
                    currentTextItem = "";
                  }
                  // Add tool use block
                  const toolUse = jsonData.event.contentBlockStart.start.toolUse;
                  currentToolName = toolUse.name;
                  // Set current working tool ID for loading state
                  setCurrentWorkingToolId(toolUse.toolUseId);
                  textArray.push({
                    type: "tool",
                    toolUseId: toolUse.toolUseId,
                    name: toolUse.name,
                    inputs: "",
                  });
                } else if (jsonData.toolUseId && jsonData.name) {
                  // Tool use input update
                  const lastItem = textArray[textArray.length - 1];
                  if (
                    lastItem &&
                    lastItem.type === "tool" &&
                    lastItem.toolUseId === jsonData.toolUseId
                  ) {
                    const inputs = JSON.parse(jsonData.input);
                    lastItem.inputs = inputs;
                    // Update current working tool ID when inputs are updated
                    setCurrentWorkingToolId(jsonData.toolUseId);
                  }
                } else if (jsonData.event?.contentBlockStop) {
                  // Content block ended - clear current working tool
                  console.log("⏹️ Content block stopped");
                } else if (jsonData.start_event_loop) {
                  // Handle start event loop
                  console.log(
                    "🔄 Start event loop received:",
                    jsonData.start_event_loop
                  );
                  currentToolName = "";
                } else if (jsonData.data) {
                  // Regular data chunk - check for error messages
                  if (typeof jsonData.data === 'string') {
                    // Check for Bedrock service errors in the data content
                    if (jsonData.data.includes("serviceUnavailableException") ||
                      jsonData.data.includes("Bedrock is unable to process your request") ||
                      jsonData.data.includes("I apologize, but I encountered an error")) {
                      console.error("🚨 Bedrock Service Error detected in data:", jsonData.data);
                      throw new Error("Bedrock service is currently unavailable. Please try again in a few moments.");
                    }
                  }

                  currentToolName = "";
                  currentTextItem += jsonData.data;
                  responseText += jsonData.data;
                  setCurrentWorkingToolId(null);
                } else {
                  console.log("❓ Unknown event type:", jsonData);
                }
              } catch (e) {
                console.error("Error processing data object:", jsonData, e);
              }
            }

            // Update UI with current progress
            setAnswers((prev) => {
              const newAnswers = [...prev];
              const lastIndex = newAnswers.length - 1;
              const currentArray = [...textArray];

              // Add current text if exists
              if (currentTextItem.trim()) {
                currentArray.push({ type: "text", content: currentTextItem });
              }

              newAnswers[lastIndex] = {
                ...newAnswers[lastIndex],
                text: currentArray,
                currentToolName,
              };
              return newAnswers;
            });
          }
        } finally {
          reader.releaseLock();
        }
      } else {
        // Handle non-streaming response (fallback)
        const bytes = await response.response.transformToByteArray();
        responseText = new TextDecoder().decode(bytes);
        currentTextItem = responseText;
        textArray = [{ type: "text", content: responseText }];

        console.log("📝 Agent Response (Non-streaming):", responseText);
      }
    } catch (streamError) {
      console.error("Error processing agent response stream:", streamError);
      throw streamError;
    }

    // Final update with complete text
    setAnswers((prev) => {
      const newAnswers = [...prev];
      const lastIndex = newAnswers.length - 1;
      const finalArray = [...textArray];

      // Add any remaining text that wasn't added during streaming
      if (currentTextItem.trim()) {
        finalArray.push({ type: "text", content: currentTextItem });
      }

      newAnswers[lastIndex] = {
        ...newAnswers[lastIndex],
        text: finalArray,
        queryUuid,
      };
      return newAnswers;
    });

    console.log("📝 Complete Agent Response:", responseText);

    // After streaming is complete, fetch query results for charts/tables
    try {
      const queryResults = await getQueryResults(queryUuid);
      console.log("📊 Query Results:", queryResults);

      if (queryResults.length > 0) {
        // Update the answer with query results
        setAnswers((prev) => {
          const newAnswers = [...prev];
          const lastIndex = newAnswers.length - 1;
          newAnswers[lastIndex] = {
            ...newAnswers[lastIndex],
            queryResults: queryResults,
            chart: "loading", // Indicate chart generation is starting
          };
          return newAnswers;
        });
      }
    } catch (queryError) {
      console.error("Error fetching query results:", queryError);
    }

    setLoading(false);
    setEnabled(false);
    // Clear current working tool when processing is complete
    setCurrentWorkingToolId(null);

  } catch (error) {
    console.log("❌ Call failed:", error);
    if (error.message.includes("Bedrock service is currently unavailable")) {
      setErrorMessage(
        "🚨 Bedrock AI service is temporarily unavailable. Please try again in a few moments."
      );
    } else if (error.message.includes("ERR_HTTP2_PROTOCOL_ERROR")) {
      setErrorMessage(
        "Connection protocol error. Response may be complete despite the error."
      );
    } else if (error.message.includes("ERR_INCOMPLETE_CHUNKED_ENCODING")) {
      setErrorMessage(
        "Connection interrupted. Partial response may be available."
      );
    } else {
      setErrorMessage(error.toString());
    }
    setLoading(false);
    setEnabled(false);
    // Clear current working tool on error
    setCurrentWorkingToolId(null);

    // Update the streaming answer with error state
    setAnswers((prevState) => {
      const newState = [...prevState];
      for (let i = newState.length - 1; i >= 0; i--) {
        if (newState[i].text && Array.isArray(newState[i].text)) {
          newState[i] = {
            ...newState[i],
            text: [{ type: "text", content: "Error occurred while getting response" }],
            error: true,
          };
          break;
        }
      }
      return newState;
    });
  }
};