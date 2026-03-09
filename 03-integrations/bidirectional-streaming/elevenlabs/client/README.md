# Bi-Directional Streaming Example App

This is a sample application demonstrating how to use the bi-directional streaming React components.

## Features

- WebSocket connection management
- Real-time audio streaming (recording and playback)
- Message display with different types (user, assistant, system, tool)
- Event logging for debugging
- Clean, modular component usage

## Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- A WebSocket endpoint that supports bi-directional audio streaming

## Installation

```bash
# Install dependencies
npm install
# or
yarn install
# or
pnpm install
```

## Running the Example

```bash
# Start development server
npm run dev
# or
yarn dev
# or
pnpm dev
```

The app will open automatically at `http://localhost:3000`.

## Usage

1. **Enter WebSocket URL**: Paste your WebSocket endpoint URL in the input field
   - For AWS Bedrock AgentCore, use a pre-signed URL with SigV4 authentication
   - Example: `wss://your-endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&...`

2. **Start Connection**: Click the "🚀 Start Connection" button
   - The app will connect to the WebSocket
   - Microphone access will be requested automatically
   - Audio recording will start once connected

3. **Speak**: Once recording starts, speak into your microphone
   - Audio is captured at 16kHz PCM format
   - Audio chunks are sent to the WebSocket endpoint
   - Transcripts and responses will appear in the Messages panel

4. **View Activity**:
   - **Messages Panel**: See conversation messages (user, assistant, system, tool)
   - **Events Panel**: View raw WebSocket events for debugging

5. **End Connection**: Click "🛑 End Connection" to disconnect

## Component Usage

The example demonstrates using all the modular components:

### ConnectionButton
```tsx
<ConnectionButton
  status={status}
  onConnect={handleConnect}
  onDisconnect={handleDisconnect}
  connectText="🚀 Start Connection"
  disconnectText="🛑 End Connection"
/>
```

### MessageList
```tsx
<MessageList messages={messages} autoScroll={true} />
```

### EventList
```tsx
<EventList events={events} autoScroll={true} />
```

### Hooks
```tsx
const { playAudio, stopAudio, resetPlaybackTiming } = useAudioPlayer();
const { startRecording, stopRecording, isRecording } = useAudioRecorder();
const { status, connect, disconnect, send } = useWebSocket({
  onMessage: handleWebSocketMessage,
  onOpen: () => { /* ... */ },
  onClose: () => { /* ... */ },
  onError: (error) => { /* ... */ },
});
```

## Customization

You can customize the app by:

1. **Custom Message Rendering**: Pass a `renderMessage` prop to `MessageList`
2. **Custom Event Rendering**: Pass a `renderEvent` prop to `EventList`
3. **Styling**: Modify the CSS or create your own styles
4. **Additional Features**: Add your own UI elements using the hooks

## Message Types

The app handles these WebSocket message types:

- `bidi_audio_stream` - Incoming audio from the assistant
- `bidi_transcript_stream` - Transcribed text (user or assistant)
- `bidi_interruption` - Signal to stop current audio playback
- `tool_use_stream` - Tool invocation by the assistant
- `tool_result` - Results from tool execution

## Troubleshooting

### Microphone Access Denied
- Check browser permissions for microphone access
- Use HTTPS or localhost (HTTP) - browsers require secure context for microphone

### WebSocket Connection Fails
- Verify the WebSocket URL is correct
- Check if the endpoint requires authentication (e.g., SigV4 for AWS)
- Ensure the endpoint supports the expected message protocol

### No Audio Playback
- Check browser console for errors
- Verify the incoming audio format matches expectations (16kHz PCM)
- Ensure audio context is not suspended (user interaction required)

## Building for Production

```bash
npm run build
# or
yarn build
# or
pnpm build
```

The built files will be in the `dist` directory.

## Learn More

- [Component Library README](../README.md)
- [TypeScript Types](../types.ts)
- [Hooks Documentation](../hooks/)
