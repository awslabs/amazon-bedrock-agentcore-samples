import { NextRequest, NextResponse } from "next/server"
import { getPolicyStatus, createPolicyEngine, addPolicy, deletePolicy, attachPolicy, detachPolicy } from "@/lib/aws"

export async function GET(req: NextRequest) {
  const gw = req.nextUrl.searchParams.get("gateway")
  if (!gw) return NextResponse.json({ error: "gateway required" }, { status: 400 })
  return NextResponse.json(await getPolicyStatus(gw))
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { action } = body
  try {
    if (action === "create-engine") {
      const out = await createPolicyEngine(body.name)
      await attachPolicy(body.name, body.gateway, "LOG_ONLY")
      return NextResponse.json({ ok: true, output: out })
    }
    if (action === "add-policy") return NextResponse.json({ ok: true, output: await addPolicy(body.engine, body.name, body.statement) })
    if (action === "delete-policy") return NextResponse.json({ ok: true, output: await deletePolicy(body.engine, body.name) })
    if (action === "attach") return NextResponse.json({ ok: true, output: await attachPolicy(body.engine, body.gateway, body.mode) })
    if (action === "detach") return NextResponse.json({ ok: true, output: await detachPolicy(body.gateway) })
    return NextResponse.json({ error: "unknown action" }, { status: 400 })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
