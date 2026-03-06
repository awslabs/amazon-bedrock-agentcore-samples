import { NextRequest, NextResponse } from "next/server"
import { getGatewayTools } from "@/lib/aws"

export async function GET(req: NextRequest) {
  const gw = req.nextUrl.searchParams.get("gateway")
  if (!gw) return NextResponse.json({ error: "gateway required" }, { status: 400 })
  return NextResponse.json(await getGatewayTools(gw))
}
