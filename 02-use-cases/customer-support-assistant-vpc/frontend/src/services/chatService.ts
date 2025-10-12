/**
 * Invoke Bedrock AgentCore endpoint with streaming
 */
export async function* invokeAgentStream(
  agentArn: string,
  region: string,
  sessionId: string,
  bearerToken: string,
  prompt: string,
  actorId: string
): AsyncGenerator<string, void, unknown> {
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
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    if (!response.body) {
      throw new Error('Response body is null')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastWasData = false

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim() === '') {
          continue
        }

        if (line.startsWith('data: ')) {
          lastWasData = true
          const data = line.substring(6).replace(/"/g, '')
          yield data
        } else if (line.trim()) {
          if (lastWasData) {
            const data = line.replace(/"/g, '')
            yield '\n' + data
          }
          lastWasData = false
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      if (buffer.startsWith('data: ')) {
        const data = buffer.substring(6).replace(/"/g, '')
        yield data
      }
    }
  } catch (error) {
    console.error('Error invoking agent endpoint:', error)
    throw error
  }
}
