import { NextRequest, NextResponse } from "next/server"
import { listRegistry } from "@/lib/db"
import { listGateways, getGatewayTools } from "@/lib/aws"

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") || ""
  const protocol = req.nextUrl.searchParams.get("protocol")
  const type = req.nextUrl.searchParams.get("type") || "all"
  const results: Record<string, unknown>[] = []

  if (type === "all" || type === "agents") {
    let entries = await listRegistry(q || undefined)
    if (protocol) entries = entries.filter(e => e.protocol === protocol)
    for (const s of entries) {
      results.push({
        type: "agent", name: s.name, description: s.description, protocol: s.protocol, version: s.version, owner: s.owner, tags: s.tags,
        endpoint: s.endpointUrl || null, runtimeArn: s.runtimeArn || null, gatewayName: s.gatewayName || null, targetName: s.targetName || null,
        tools: s.tools.map(t => ({ name: t.shortName, description: t.description })),
        skills: (() => { try { return JSON.parse(s.skills).map((sk: Record<string, string>) => ({ name: sk.name || sk.id, description: sk.description })) } catch { return [] } })(),
      })
    }
  }

  if ((type === "all" || type === "gateways") && (!protocol || protocol === "mcp")) {
    try {
      const gateways = await listGateways()
      for (const gw of gateways) {
        if (gw.status !== "READY") continue
        let tools: { name: string; description: string }[] = []
        try { const groups = await getGatewayTools(gw.name); tools = groups.flatMap(g => g.tools.map(t => ({ name: t.name, description: t.description }))) } catch {}
        if (q && !gw.name.toLowerCase().includes(q.toLowerCase()) && !tools.some(t => t.name.toLowerCase().includes(q.toLowerCase()) || (t.description || "").toLowerCase().includes(q.toLowerCase()))) continue
        results.push({
          type: "gateway", name: gw.name, description: `AgentCore MCP Gateway — ${tools.length} tools across multiple targets`, protocol: "mcp", gatewayId: gw.id,
          mcpConfig: { url: `https://${gw.id}.gateway.bedrock-agentcore.${process.env.GATEWAY_REGION || "us-east-1"}.amazonaws.com/mcp`, note: "Requires JWT token. Use: gatewayctl gateway get-token --name " + gw.name },
          tools,
        })
      }
    } catch {}
  }

  return NextResponse.json({ agents: results, count: results.length, query: q || undefined })
}
