# Tool Display Debugging Guide

## Problem Summary
Tools are not being displayed in the chat UI even though they are being invoked by the backend.

## Root Cause Analysis

### Backend Issue
Your backend is sending events in **two different formats**:

1. **Proper AWS Bedrock JSON format** (✅ parsed correctly):
   ```
   data: {"event": {"contentBlockDelta": {"delta": {"text": "..."}, "contentBlockIndex": 0}}}
   ```

2. **Python debug string format** (❌ cannot be parsed):
   ```
   data: "{'data': '...', 'agent': <strands.agent.agent.Agent object at 0xffff8e5574d0>, ...}"
   ```

The Python format contains:
- Single quotes instead of double quotes
- Python-specific syntax like `None`, `<object at 0x...>`, `UUID('...')`
- Cannot be parsed as valid JSON

### What's Getting Lost
The Python debug format appears to contain important tool information including:
- Tool results in `structuredContent`
- Tool invocation details
- Tool status information

Since this format cannot be parsed as JSON, this information is being discarded.

## Debug Steps

### 1. Run the application and send a message that triggers tools
```bash
npm run dev
```

### 2. Check the console logs for these key indicators:

#### a) Event Parsing Issues
Look for:
```
[useChat] Event is not an object, skipping: string
```
This means the Python debug format is being rejected.

#### b) Content Block Building
Look for:
```
[useChat] 📦 Building content blocks. Indices: [...] Tool count: X
[useChat] 🔧 Tool started: <tool_name> at index X
[useChat] ✍️ Added text block at index X length: X
[useChat] 🔧 Added tool block at index X : <tool_name> status: <status>
```

#### c) Final Summary
After streaming completes, look for:
```
[useChat] ✅ Stream complete!
[useChat] 📊 Summary:
  - Accumulated response length: X
  - Total tools: X
  - Tool names: [...]
  - Elapsed time: X s

[useChat] 💾 Final message state:
  - Content length: X
  - Content blocks: X
  - Tool blocks: X
```

#### d) Rendering
Look for:
```
[ChatMessage] Rendering assistant message with X content blocks
[ChatMessage] 🔧 Rendering X tool blocks: [tool names]
```

### 3. Diagnose Based on Logs

#### Case 1: Tools captured but not rendered
**Symptoms:**
- ✅ `Total tools: > 0`
- ✅ `Content blocks: > 0`
- ❌ No `[ChatMessage] 🔧 Rendering` logs

**Cause:** UI rendering issue
**Solution:** Check if `contentBlocks` prop is being passed correctly to ChatMessage

#### Case 2: Tools not captured at all
**Symptoms:**
- ❌ `Total tools: 0`
- ❌ No `🔧 Tool started:` logs
- ✅ Only text deltas received

**Cause:** Backend not sending proper tool events
**Solution:** Fix backend to send tool information in valid JSON format

#### Case 3: Tools captured but missing details
**Symptoms:**
- ✅ `Total tools: > 0`
- ✅ `🔧 Tool started:` logs
- ❌ No tool results or incomplete tool data

**Cause:** Tool results only in Python debug format
**Solution:** Backend must send tool results in proper JSON format

## Solutions

### Backend Fix (RECOMMENDED)
The backend should:
1. **Stop sending Python debug format** - This is likely coming from a print statement or debug logger
2. **Send only valid JSON in SSE format** with proper tool events:
   ```json
   data: {"event": {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "...", "name": "..."}}, "contentBlockIndex": 0}}}
   data: {"event": {"contentBlockDelta": {"delta": {"toolUse": {"input": "..."}}, "contentBlockIndex": 0}}}
   data: {"event": {"contentBlockStop": {"contentBlockIndex": 0}}}
   ```

Or send tool information in `message` events:
```json
data: {"message": {"role": "assistant", "content": [{"toolUse": {"toolUseId": "...", "name": "...", "input": {...}}}]}}
```

### Frontend Workaround (TEMPORARY)
If you cannot fix the backend immediately, you could try to parse the Python format, but this is **not recommended** because:
- Fragile and error-prone
- Python syntax is not valid JSON
- Object references like `<strands.agent.agent.Agent object at 0xffff8e5574d0>` cannot be converted
- Values like `None`, `True`, `False` need conversion to JSON equivalents

## Next Steps

1. **Run the app and collect logs** based on the steps above
2. **Share the complete log output** starting from:
   - `[chatService] Starting to read stream...`
   - Through all the `[useChat]` logs
   - Up to `[useChat] ✅ Stream complete!`

3. **Check your backend code** for:
   - Any `print()` statements that might be outputting to the SSE stream
   - Debug loggers that write to stdout
   - Ensure only proper SSE events are sent to the response stream

4. **Verify the event format** your backend should be sending - it should match AWS Bedrock's streaming format or your custom defined format, but always as **valid JSON**.

## Expected Behavior

When working correctly, you should see:
1. ✅ No "Event is not an object, skipping" warnings
2. ✅ `🔧 Tool started:` logs for each tool invocation
3. ✅ `Total tools: X` where X > 0
4. ✅ `Content blocks: Y` where Y includes tool blocks
5. ✅ `[ChatMessage] 🔧 Rendering X tool blocks:` with tool names
6. ✅ Tool blocks visible in the UI with expand/collapse functionality

## Contact
If you need further help, share:
- Complete console logs from a single message interaction
- Your backend SSE event generation code
- Screenshots of what you see (or don't see) in the UI
