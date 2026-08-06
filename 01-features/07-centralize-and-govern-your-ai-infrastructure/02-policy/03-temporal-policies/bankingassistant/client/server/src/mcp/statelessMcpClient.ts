import { log } from "../logger.js";
import {
  McpClient,
  McpClientDeps,
  McpTool,
  POLICY_SESSION_HEADER,
  ProtocolVersion,
  SessionInvalidatedError,
  ToolCallResult,
} from "./types.js";

/**
 * MCP client for the 2026-07-28 STATELESS protocol revision, per
 * https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-list.html
 *
 * Stateless means no `initialize` handshake and no Mcp-Session-Id. Each request
 * is a self-contained JSON-RPC POST that carries:
 *   - header  MCP-Protocol-Version: 2026-07-28
 *   - header  Mcp-Method: <the method, e.g. tools/list, tools/call>
 *   - header  Mcp-Name: <the tool name> (required for tools/call)
 *   - params._meta with the protocol version, client info, and capabilities
 *
 * The gateway enforces that these headers match the body, so Mcp-Name must equal
 * params.name on tools/call. Tools are listed with `tools/list` (not
 * server/discover). Everything protocol-specific is confined to this file;
 * DEBUG_MCP=1 logs raw traffic.
 */
const VERSION: ProtocolVersion = "2026-07-28";
const META_VERSION = "io.modelcontextprotocol/protocolVersion";
const META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo";
const META_CLIENT_CAPS = "io.modelcontextprotocol/clientCapabilities";

const CLIENT_INFO = { name: "banking-assistant-web", version: "1.0.0" };

/**
 * Parse an MCP HTTP response body. The gateway returns either plain JSON or an
 * SSE stream (`event: message\ndata: {json}\n\n`) depending on content type.
 * For SSE, return the JSON-RPC object from the last `data:` line that has one.
 */
function parseMcpBody(contentType: string | null, text: string): any {
  const isSse = (contentType ?? "").includes("text/event-stream");
  if (!isSse) return JSON.parse(text);

  let last: any = null;
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trimStart();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice(5).trim();
    if (!payload || payload === "[DONE]") continue;
    try {
      last = JSON.parse(payload);
    } catch {
      // Ignore keep-alive or non-JSON data lines.
    }
  }
  if (last === null) {
    throw new Error(`No JSON payload in SSE response: ${text.slice(0, 200)}`);
  }
  return last;
}

export function createStatelessMcpClient(deps: McpClientDeps): McpClient {
  let rpcId = 0;

  async function rpc(
    method: string,
    params: Record<string, unknown>,
    mcpName?: string,
  ): Promise<any> {
    const token = await deps.getToken();
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      "MCP-Protocol-Version": VERSION,
      "Mcp-Method": method,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    };
    // On 2026-07-28 the gateway requires an Mcp-Name header naming the tool for
    // tools/call, and rejects the request if it contradicts params.name.
    if (mcpName) headers["Mcp-Name"] = mcpName;
    const policyId = deps.getPolicySessionId();
    if (policyId) headers[POLICY_SESSION_HEADER] = policyId;

    const body = {
      jsonrpc: "2.0",
      id: ++rpcId,
      method,
      params: {
        ...params,
        _meta: {
          [META_VERSION]: VERSION,
          [META_CLIENT_INFO]: CLIENT_INFO,
          [META_CLIENT_CAPS]: {},
        },
      },
    };

    log.debug("stateless MCP request", { method, body });

    const res = await fetch(deps.mcpUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    const returned = res.headers.get(POLICY_SESSION_HEADER);
    if (returned && returned !== deps.getPolicySessionId()) {
      deps.onPolicySessionId(returned);
    }
    if (res.status === 409) throw new SessionInvalidatedError();

    const text = await res.text();
    log.debug("stateless MCP response", { status: res.status, text });
    if (!res.ok) {
      throw new Error(`MCP ${method} failed (${res.status}): ${text}`);
    }

    // The gateway may reply as plain JSON or as an SSE stream (text/event-stream)
    // when streaming is enabled. Handle both.
    const json = parseMcpBody(res.headers.get("content-type"), text);
    if (json.error) {
      throw new Error(`MCP ${method} error: ${JSON.stringify(json.error)}`);
    }
    return json.result;
  }

  return {
    protocol: VERSION,
    mcpSessionId: null, // stateless: no transport session
    get policySessionId() {
      return deps.getPolicySessionId();
    },

    async connect(): Promise<void> {
      // No handshake in the stateless protocol.
    },

    async listTools(): Promise<McpTool[]> {
      const result = await rpc("tools/list", {});
      const tools = (result?.tools ?? []) as Array<{
        name: string;
        description?: string;
        inputSchema?: Record<string, unknown>;
      }>;
      return tools.map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: t.inputSchema ?? { type: "object", properties: {} },
      }));
    },

    async callTool(
      name: string,
      args: Record<string, unknown>,
    ): Promise<ToolCallResult> {
      const result = await rpc("tools/call", { name, arguments: args }, name);
      return { content: result?.content ?? result, isError: Boolean(result?.isError) };
    },

    async close(): Promise<void> {
      // Nothing to tear down.
    },
  };
}
