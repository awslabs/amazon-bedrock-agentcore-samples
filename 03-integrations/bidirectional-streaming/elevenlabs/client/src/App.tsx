import React, { useState, useCallback } from "react";
import toast, { Toaster } from "react-hot-toast";
import {
  MessageList,
  EventList,
  useWebSocket,
  useAudioRecorder,
  useAudioPlayer,
  useMessageHandler,
} from "strands-client-react";
import { ConnectionButton } from "./ConnectionButton";
import "./styles.css";
import "./App.css";

export const App: React.FC = () => {
  const [url, setUrl] = useState("");
  const [theme, setTheme] = useState<"light" | "dark" | "calm">("light");
  const [layout, setLayout] = useState<"default" | "stripped">("default");
  const [showAllMessages, setShowAllMessages] = useState(true);
  const [showTools, setShowTools] = useState(true);
  const [hideAudioInput, setHideAudioInput] = useState(true);

  const { playAudio, stopAudio, resetPlaybackTiming } = useAudioPlayer();
  const { startRecording, stopRecording, isRecording } = useAudioRecorder();

  const { messages, events, addEvent, handleWebSocketMessage, clearAll } =
    useMessageHandler({
      onAudioStream: async (audio, sampleRate) => {
        await playAudio(audio, sampleRate);
      },
      onInterruption: () => {
        stopAudio();
        resetPlaybackTiming();
      },
    });

  const { status, connect, disconnect, send } = useWebSocket({
    onMessage: handleWebSocketMessage,
    onOpen: () => {
      toast.success("Connected to WebSocket");
      handleStartRecording();
    },
    onClose: () => {
      toast("Disconnected from WebSocket");
      if (isRecording()) {
        stopRecording();
      }
      stopAudio();
    },
    onError: (error) => {
      toast.error(`Error: ${error.message}`);
    },
  });

  const handleStartRecording = useCallback(async () => {
    try {
      await startRecording(
        (audioMessage: any) => {
          send(audioMessage);
          if (!hideAudioInput)
            addEvent("sent", "bidi_audio_input", audioMessage);
        },
        { echoCancellation: true }
      );
      toast.success("Recording started - speak now");
    } catch (error) {
      toast.error(`Microphone error: ${(error as Error).message}`);
    }
  }, [startRecording, send, addEvent]);

  const handleConnect = useCallback(async () => {
    if (!url) {
      toast.error("URL is required");
      return;
    }

    if (!url.startsWith("ws://") && !url.startsWith("wss://")) {
      toast.error("URL must start with ws:// or wss://");
      return;
    }

    clearAll();
    //toast.loading(`Connecting to: ${url}`, {});

    try {
      await connect(url);
    } catch (error) {
      toast.error(`Failed to connect: ${(error as Error).message}`);
    }
  }, [url, connect, clearAll]);

  const handleDisconnect = useCallback(() => {
    if (isRecording()) {
      stopRecording();
    }
    disconnect();
  }, [disconnect, isRecording, stopRecording]);

  return (
    <div
      className={`strands-container ${theme === "calm" ? "theme-calm" : "theme-default"} ${theme === "dark" ? "bidi-dark" : ""} ${layout === "stripped" ? "layout-stripped" : ""}`}
    >
      <Toaster position="top-right" />
      <div className="strands-content">
        <div className="config-section">
          <div className="form-group">
            <label htmlFor="websocket-url">
              WebSocket URL (with SigV4 if needed)
            </label>
            <input
              type="text"
              id="websocket-url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="wss://your-websocket-endpoint"
              disabled={status !== "disconnected"}
            />
            <small>
              Enter your WebSocket connection URL (e.g., with pre-signed SigV4
              parameters)
            </small>
          </div>
        </div>

        <div className="controls">
          <ConnectionButton
            status={status}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            connectText="Start Connection"
            disconnectText="End Connection"
          />
          <div className="theme-selector">
            <label htmlFor="layout-select">Layout:</label>
            <select
              id="layout-select"
              value={layout}
              onChange={(e) =>
                setLayout(e.target.value as "default" | "stripped")
              }
            >
              <option value="default">Default</option>
              <option value="stripped">Stripped</option>
            </select>
          </div>
          <div className="theme-selector">
            <label htmlFor="theme-select">Theme:</label>
            <select
              id="theme-select"
              value={theme}
              onChange={(e) =>
                setTheme(e.target.value as "light" | "dark" | "calm")
              }
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="calm">Calm</option>
            </select>
          </div>
          {layout !== "stripped" && (
            <>
              <div className="theme-selector">
                <label htmlFor="message-filter">Messages:</label>
                <select
                  id="message-filter"
                  value={showAllMessages ? "all" : "summary"}
                  onChange={(e) => setShowAllMessages(e.target.value === "all")}
                >
                  <option value="all">Show All</option>
                  <option value="summary">Summary Only</option>
                </select>
              </div>
              <div className="theme-selector">
                <label htmlFor="tool-filter">Tool Messages:</label>
                <select
                  id="tool-filter"
                  value={showTools ? "show" : "hide"}
                  onChange={(e) => setShowTools(e.target.value === "show")}
                >
                  <option value="show">Show</option>
                  <option value="hide">Hide</option>
                </select>
              </div>
              <div className="theme-selector">
                <label htmlFor="audio-input-filter">Audio Input:</label>
                <select
                  id="audio-input-filter"
                  value={hideAudioInput ? "hide" : "show"}
                  onChange={(e) => setHideAudioInput(e.target.value === "hide")}
                >
                  <option value="hide">Hide</option>
                  <option value="show">Show</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div className="panels-container">
          <div className="panel">
            {layout !== "stripped" && <h2>Messages</h2>}
            <MessageList
              messages={messages}
              autoScroll={true}
              showAllMessages={layout === "stripped" ? false : showAllMessages}
              showTools={layout === "stripped" ? false : showTools}
            />
          </div>

          {layout !== "stripped" && (
            <div className="panel">
              <h2>Events</h2>
              <EventList
                events={events}
                autoScroll={true}
                hideAudioInput={hideAudioInput}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
