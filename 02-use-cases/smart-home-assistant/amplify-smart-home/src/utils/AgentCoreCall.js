import { v4 as uuidv4 } from "uuid";
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";
import { createAwsClient } from "./AwsAuth";
import { getMediaAssets } from "./AwsCalls";

export const getAnswer = async (
  my_query,
  sessionId,
  setControlAnswers,
  setAnswers,
  setEnabled,
  setLoading,
  setErrorMessage,
  setQuery,
  setCurrentWorkingToolId,
  assistantConfig = {},
  userName = "",
  email = ""
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
    console.log("⚙️ Assistant Config:", assistantConfig);
    console.log("🌍 Agent Region:", assistantConfig.agent?.region);

    // Add initial answer object to state
    setControlAnswers((prevState) => [
      ...prevState,
      { current_tab_view: "answer" },
    ]);
    setAnswers((prevState) => [...prevState, json]);

    // Create AWS client for Bedrock Agent Core with region from assistant config
    const agentRegion = assistantConfig.agent?.region;
    const clientOptions = agentRegion ? { region: agentRegion } : {};
    const agentCore = await createAwsClient(BedrockAgentCoreClient, clientOptions);

    // Create the payload for the agent
    const payload = JSON.stringify({
      prompt: my_query,
      session_id: sessionId,
      user_name: userName,
      user_email: email,
      prompt_uuid: queryUuid,
      //user_timezone: timezone,
      //last_k_turns: 10,
    });

    const input = {
      agentRuntimeArn: assistantConfig.agent?.runtimeArn,
      qualifier: assistantConfig.agent?.endpointName,
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
    let hasReceivedFirstChunk = false;

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

            // Process streaming data - Extract data objects from AWS SDK format
            const dataObjects = [];
            let currentToolName = "";

            try {
              chunk.split("\n").forEach((line) => {
                if (line.trim() && line.startsWith("data: ")) {
                  const jsonString = line.replace(/^data: /, '{"data": ') + "}";
                  try {
                    const obj = JSON.parse(jsonString);
                    const data_object = JSON.parse(obj.data);
                    
                    // Check if the parsed data contains an error
                    if (data_object.error) {
                      console.error("❌ Error in chunk data:", data_object);
                      const errorMsg = data_object.message || data_object.error;
                      const errorType = data_object.error_type || "Error";
                      const errorDetail = data_object.error;
                      
                      // Add error as text to display in conversation
                      const errorText = `**${errorType}**: ${errorDetail}\n\n${errorMsg}`;
                      currentTextItem += errorText;
                      responseText += errorText;
                      
                      // Show error alert
                      setErrorMessage(`${errorType}: ${errorMsg}`);
                      setLoading(false);
                      setEnabled(false);
                    } else {
                      // Only add non-error data objects
                      dataObjects.push(data_object);
                    }
                  } catch (error) {
                    console.error("Error parsing JSON:", error);
                  }
                }
              });
            } catch (error) {
              console.error("Error processing chunk:", error);
              setErrorMessage(`Error processing streaming data: ${error.message}`);
            }

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
                  //setCurrentWorkingToolId(null);
                } else if (jsonData.start_event_loop) {
                  // Handle start event loop
                  console.log(
                    "🔄 Start event loop received:",
                    jsonData.start_event_loop
                  );
                  
                  currentToolName = "";

                } else if (jsonData.data) {
                  // Regular data chunk
                  currentToolName = "";
                  currentTextItem += jsonData.data;
                  responseText += jsonData.data;
                  setCurrentWorkingToolId(null);
                } else {
                  console.log("❓ Unknown event type:", jsonData);
                }
              } catch (e) {
                console.log("Error processing data object:", jsonData, e);
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
      };
      return newAnswers;
    });

    console.log("📝 Complete Agent Response:", responseText);

    // After streaming is complete, fetch media assets if needed
    const mediaAssets = await getMediaAssets(queryUuid, assistantConfig);
    console.log("🤖 Final Media Assets:", mediaAssets);

    setLoading(false);
    setEnabled(false);
    // Clear current working tool when processing is complete
    setCurrentWorkingToolId(null);

    // Update the answer with media assets if available
    if (mediaAssets.length > 0) {
      setAnswers((prev) => {
        const newAnswers = [...prev];
        const lastIndex = newAnswers.length - 1;
        newAnswers[lastIndex] = {
          ...newAnswers[lastIndex],
          mediaAssets: mediaAssets,
          chart: true,
        };
        return newAnswers;
      });

      console.log("✨ Answer with media assets:");
      console.log({
        text: responseText,
        queryUuid,
        mediaAssets,
      });
    } else {
      console.log("📄 Answer without media assets:");
      console.log({ text: responseText, queryUuid });
    }

  } catch (error) {
    console.log("❌ Call failed:", error);
    if (error.message.includes("ERR_HTTP2_PROTOCOL_ERROR")) {
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
  }
};
