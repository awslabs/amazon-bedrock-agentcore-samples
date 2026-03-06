import { NextResponse } from "next/server"
import { listGateways } from "@/lib/aws"

export async function GET() {
  return NextResponse.json(await listGateways())
}
