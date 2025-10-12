# Sequential Agentic Workflow Display - Fix Summary

## Problem
The frontend was grouping content by `contentBlockIndex`, but the backend sends multiple assistant messages (one per event loop cycle) that ALL use index 0. This caused tools and text from later cycles to be missed or overwritten.

The user wanted to see the complete agentic workflow in ONE message:
```
Text: "I'll analyze..."
  ↓
Tool: run_query
  ↓
Text: "Now let me get..."
  ↓
Tool: get_customer_profile (×3)
  ↓
Text: "Now let me check..."
  ↓
Tool: run_query
  ↓
Text: "Here's the analysis..."
```

## Root Cause
Backend sends:
- Multiple `assistant` messages in the conversation history
- Each has `contentBlockIndex: 0` for its content
- Frontend was treating index as unique, causing collisions

## Solution
**Changed from index-based grouping to sequential timeline:**

### Before (Index-Based)
```typescript
contentBlocksByIndex: Map<number, Array<ContentBlock>>
// Problem: Index 0 gets reused, causing overwrites
```

### After (Sequential Timeline)
```typescript
orderedContent: Array<ContentBlock>
currentTextBlock: TextBlock | null
// Solution: Append everything in order received
```

## Key Changes

### 1. Data Structure (src/hooks/useChat.tsx:67-69)
```typescript
// OLD: Map indexed by contentBlockIndex
const contentBlocksByIndex: Map<number, Array<...>> = new Map();

// NEW: Sequential array + current text accumulator
const orderedContent: Array<...> = [];
let currentTextBlock: { type: 'text'; content: string } | null = null;
```

### 2. Text Handling (src/hooks/useChat.tsx:134-142)
```typescript
// When text arrives:
if (!currentTextBlock) {
  currentTextBlock = { type: 'text', content: '' };
}
currentTextBlock.content += delta.text;
// Accumulate in current block until interrupted by tool
```

### 3. Tool Handling (src/hooks/useChat.tsx:103-124)
```typescript
// When tool starts:
// 1. Finalize current text block
if (currentTextBlock && currentTextBlock.content) {
  orderedContent.push({ ...currentTextBlock });
  currentTextBlock = null;
}

// 2. Add tool to sequential list
orderedContent.push({
  type: 'tool',
  toolBlock: newToolBlock,
  toolUseId: toolUseId,
});
```

### 4. Final Assembly (src/hooks/useChat.tsx:333-367)
```typescript
// Before building final array, finalize any pending text
if (currentTextBlock && currentTextBlock.content) {
  orderedContent.push({ ...currentTextBlock });
}

// Build final content blocks maintaining order
for (const item of orderedContent) {
  if (item.type === 'text') {
    orderedContentBlocks.push({ type: 'text', content: item.content });
  } else if (item.type === 'tool') {
    // Get latest state from toolBlocks map
    const latestToolBlock = toolBlocks.get(item.toolUseId);
    orderedContentBlocks.push({ type: 'tool', toolBlock: latestToolBlock });
  }
}
```

## Flow Diagram

```
Stream Event → Handler
─────────────────────────

Text Delta
    ↓
  Accumulate in currentTextBlock
    ↓
  Continue accumulating...

Tool Start
    ↓
  Finalize currentTextBlock → orderedContent.push()
    ↓
  Add tool → orderedContent.push()
    ↓
  currentTextBlock = null

Text Delta (after tool)
    ↓
  Create new currentTextBlock
    ↓
  Accumulate text...

Stream End
    ↓
  Finalize any pending currentTextBlock
    ↓
  Build orderedContentBlocks from orderedContent
```

## Result

Now displays complete agentic workflow in one message:
1. ✅ All text segments preserved in order
2. ✅ All tools displayed in execution order
3. ✅ Multiple tools at same index work correctly
4. ✅ Text between tools creates natural conversation flow

## Debug Logs

Look for these logs to verify correct behavior:
```
[useChat] ✍️ Added text block, length: X preview: "..."
[useChat] 🔧 Added tool block: tool_name status: success
[useChat] 📦 Final workflow:
  [0] 💬 "I'll analyze customer value, product prefer..."
  [1] 🔧 run_query
  [2] 💬 "Now let me get their support engagement le..."
  [3] 🔧 prod-customer-support-vpc___get_customer_profile
  [4] 🔧 prod-customer-support-vpc___get_customer_profile
  [5] 🔧 prod-customer-support-vpc___get_customer_profile
  [6] 💬 "Now let me check what products these valuab..."
  [7] 🔧 run_query
```

## Additional Improvements

### Tool Results Expanded by Default (src/components/ToolUseBlock.tsx:13)
```typescript
// Changed from false to true
const [showResult, setShowResult] = useState(true);
```
This makes the agentic workflow more visible without requiring clicks.

## Testing

1. Send query: "Which customers are most valuable and what products do they prefer?"
2. Observe console logs showing sequential workflow
3. Verify UI displays all text and tools in correct order
4. Check that tool results are visible (expanded by default)
