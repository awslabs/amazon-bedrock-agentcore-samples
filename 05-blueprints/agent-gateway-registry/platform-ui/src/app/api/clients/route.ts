import { NextRequest, NextResponse } from "next/server"
import { listClients, addClient, revokeClient, createAgentClient, createPermitPolicy } from "@/lib/aws"

export async function GET(req: NextRequest) {
  const gw = req.nextUrl.searchParams.get("gateway")
  if (!gw) return NextResponse.json({ error: "gateway required" }, { status: 400 })
  return NextResponse.json(await listClients(gw))
}

export async function POST(req: NextRequest) {
  const { gateway, clientName, allowedTools, type, workloadName } = await req.json()
  if (!gateway || !clientName) return NextResponse.json({ error: "gateway and clientName required" }, { status: 400 })

  // Create the client (Cognito app client + gateway allowedClients)
  const result = await addClient(gateway, clientName)

  // Create agent workload identity if agent type
  let workload
  if (type === "agent" && workloadName) {
    workload = await createAgentClient(workloadName)
  }

  // If tool restrictions specified, create permit-only Cedar policy
  // This replaces the old forbid-unless pattern
  let policyResult
  if (allowedTools) {
    const toolNames = allowedTools.split(",").map((t: string) => t.trim()).filter(Boolean)
    // Get the client ID from the newly created client
    const clients = await listClients(gateway)
    const newClient = clients.find(c => c.name.includes(clientName))
    if (newClient && toolNames.length) {
      policyResult = await createPermitPolicy(gateway, clientName, newClient.clientId, toolNames)
    }
  }

  return NextResponse.json({ ok: true, output: result, workload, policy: policyResult })
}

export async function DELETE(req: NextRequest) {
  const { gateway, clientName } = await req.json()
  if (!gateway || !clientName) return NextResponse.json({ error: "gateway and clientName required" }, { status: 400 })
  const result = await revokeClient(gateway, clientName)
  return NextResponse.json({ ok: true, output: result })
}
