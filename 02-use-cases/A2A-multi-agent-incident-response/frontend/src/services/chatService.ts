import type { StreamingEvent } from '../types'

/**
 * Invoke Bedrock AgentCore endpoint with streaming
 * Returns parsed streaming events as JSON objects
 */
export async function* invokeAgentStream(
  agentArn: string,
  region: string,
  sessionId: string,
  bearerToken: string,
  prompt: string,
  actorId: string
): AsyncGenerator<StreamingEvent, void, unknown> {
  const escapedArn = encodeURIComponent(agentArn)
  const url = `https://bedrock-agentcore.${region}.amazonaws.com/runtimes/${escapedArn}/invocations`

  const headers = {
    'Authorization': `Bearer ${bearerToken}`,
    'Content-Type': 'application/json',
    'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId,
  }

  const body = JSON.stringify({
    prompt: prompt,
    actor_id: actorId,
  })

  try {
    const response = await fetch(url + '?qualifier=DEFAULT', {
      method: 'POST',
      headers: headers,
      body: body,
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`)
    }

    if (!response.body) {
      throw new Error('Response body is null')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        break
      }

      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmedLine = line.trim()

        if (trimmedLine === '') {
          continue
        }

        // Handle SSE format (data: prefix)
        if (trimmedLine.startsWith('data: ')) {
          const dataContent = trimmedLine.substring(6).trim()

          // Try to parse as JSON
          try {
            const event = JSON.parse(dataContent) as StreamingEvent
            console.log('[CHAT_SERVICE] Parsed SSE event:', event)
            yield event
          } catch (parseError) {
            // Not JSON, treat as plain text (backward compatibility)
            // Remove quotes that backend might add
            const plainText = dataContent.replace(/^"|"$/g, '')
            console.log('[CHAT_SERVICE] Plain text SSE:', plainText)
            yield { data: plainText } as StreamingEvent
          }
          continue
        }

        // Try to parse as JSON event (no data: prefix)
        try {
          const event = JSON.parse(trimmedLine) as StreamingEvent
          console.log('[CHAT_SERVICE] Parsed JSON event:', event)
          yield event
        } catch (parseError) {
          // If not valid JSON, skip
          console.warn('[CHAT_SERVICE] Failed to parse streaming event:', trimmedLine)
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      try {
        const event = JSON.parse(buffer.trim()) as StreamingEvent
        yield event
      } catch (parseError) {
        // Skip unparseable final buffer
      }
    }
  } catch (error) {
    throw error
  }
}
