import { DynamoDBClient } from "@aws-sdk/client-dynamodb"
import { DynamoDBDocumentClient, PutCommand, GetCommand, QueryCommand, DeleteCommand, ScanCommand } from "@aws-sdk/lib-dynamodb"

const TABLE = process.env.DYNAMODB_TABLE || "agent-registry"
const REGION = process.env.GATEWAY_REGION || "us-east-1"

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }))

// --- Registry (McpServer equivalent) ---

export interface RegistryEntry {
  id: string
  name: string
  description?: string
  owner?: string
  repoUrl?: string
  runtimeArn?: string
  version: string
  tags: string[]
  gatewayName?: string
  targetName?: string
  protocol: string
  endpointUrl?: string
  agentCard?: string
  skills: string
  tools: ToolEntry[]
  createdAt: string
  updatedAt: string
}

export interface ToolEntry {
  id: string
  name: string
  shortName: string
  description?: string
  inputSchema?: string
}

export async function listRegistry(search?: string): Promise<RegistryEntry[]> {
  const resp = await ddb.send(new ScanCommand({ TableName: TABLE, FilterExpression: "begins_with(PK, :pk)", ExpressionAttributeValues: { ":pk": "AGENT#" } }))
  const items = (resp.Items || []) as Record<string, unknown>[]

  // Group agents and their tools
  const agents = new Map<string, RegistryEntry>()
  for (const item of items) {
    const sk = item.SK as string
    if (sk === "META") {
      const entry = itemToEntry(item)
      entry.tools = []
      agents.set(item.PK as string, entry)
    }
  }

  // Get tools
  for (const item of items) {
    const sk = item.SK as string
    if (sk.startsWith("TOOL#")) {
      const agent = agents.get(item.PK as string)
      if (agent) agent.tools.push({ id: sk, name: item.name as string, shortName: item.shortName as string, description: item.description as string | undefined })
    }
  }

  let results = Array.from(agents.values())

  if (search) {
    const q = search.toLowerCase()
    results = results.filter(a =>
      a.name.toLowerCase().includes(q) ||
      (a.description || "").toLowerCase().includes(q) ||
      a.tags.some(t => t.toLowerCase().includes(q))
    )
  }

  return results.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
}

export async function getRegistry(id: string): Promise<RegistryEntry | null> {
  const resp = await ddb.send(new GetCommand({ TableName: TABLE, Key: { PK: `AGENT#${id}`, SK: "META" } }))
  if (!resp.Item) return null
  const entry = itemToEntry(resp.Item as Record<string, unknown>)

  // Get tools
  const toolResp = await ddb.send(new QueryCommand({ TableName: TABLE, KeyConditionExpression: "PK = :pk AND begins_with(SK, :sk)", ExpressionAttributeValues: { ":pk": `AGENT#${id}`, ":sk": "TOOL#" } }))
  entry.tools = (toolResp.Items || []).map(t => ({ id: t.SK as string, name: t.name as string, shortName: t.shortName as string, description: t.description as string | undefined }))

  return entry
}

export async function createRegistry(data: Omit<RegistryEntry, "id" | "tools" | "createdAt" | "updatedAt">): Promise<RegistryEntry> {
  const id = crypto.randomUUID().slice(0, 12)
  const now = new Date().toISOString()
  await ddb.send(new PutCommand({
    TableName: TABLE,
    Item: { PK: `AGENT#${id}`, SK: "META", id, ...data, tags: JSON.stringify(data.tags), createdAt: now, updatedAt: now },
  }))
  return { ...data, id, tools: [], createdAt: now, updatedAt: now }
}

export async function updateRegistry(id: string, data: Partial<Pick<RegistryEntry, "description" | "owner" | "repoUrl" | "version" | "tags" | "agentCard" | "skills">>): Promise<void> {
  const existing = await getRegistry(id)
  if (!existing) throw new Error("Not found")
  await ddb.send(new PutCommand({
    TableName: TABLE,
    Item: {
      PK: `AGENT#${id}`, SK: "META", id,
      name: existing.name, description: data.description ?? existing.description, owner: data.owner ?? existing.owner,
      repoUrl: data.repoUrl ?? existing.repoUrl, runtimeArn: existing.runtimeArn, version: data.version ?? existing.version,
      tags: JSON.stringify(data.tags ?? existing.tags), gatewayName: existing.gatewayName, targetName: existing.targetName,
      protocol: existing.protocol, endpointUrl: existing.endpointUrl,
      agentCard: data.agentCard ?? existing.agentCard, skills: data.skills ?? existing.skills,
      createdAt: existing.createdAt, updatedAt: new Date().toISOString(),
    },
  }))
}

export async function deleteRegistry(id: string): Promise<void> {
  // Delete tools first
  const toolResp = await ddb.send(new QueryCommand({ TableName: TABLE, KeyConditionExpression: "PK = :pk AND begins_with(SK, :sk)", ExpressionAttributeValues: { ":pk": `AGENT#${id}`, ":sk": "TOOL#" } }))
  for (const t of toolResp.Items || []) {
    await ddb.send(new DeleteCommand({ TableName: TABLE, Key: { PK: `AGENT#${id}`, SK: t.SK as string } }))
  }
  await ddb.send(new DeleteCommand({ TableName: TABLE, Key: { PK: `AGENT#${id}`, SK: "META" } }))
}

export async function upsertTool(agentId: string, tool: { name: string; shortName: string; description?: string }): Promise<void> {
  await ddb.send(new PutCommand({
    TableName: TABLE,
    Item: { PK: `AGENT#${agentId}`, SK: `TOOL#${tool.shortName}`, ...tool, createdAt: new Date().toISOString() },
  }))
}

// --- Helpers ---

function itemToEntry(item: Record<string, unknown>): RegistryEntry {
  let tags: string[] = []
  try { tags = JSON.parse(item.tags as string || "[]") } catch {}
  return {
    id: item.id as string,
    name: item.name as string,
    description: item.description as string | undefined,
    owner: item.owner as string | undefined,
    repoUrl: item.repoUrl as string | undefined,
    runtimeArn: item.runtimeArn as string | undefined,
    version: (item.version as string) || "1.0.0",
    tags,
    gatewayName: item.gatewayName as string | undefined,
    targetName: item.targetName as string | undefined,
    protocol: (item.protocol as string) || "mcp",
    endpointUrl: item.endpointUrl as string | undefined,
    agentCard: item.agentCard as string | undefined,
    skills: (item.skills as string) || "[]",
    tools: [],
    createdAt: item.createdAt as string,
    updatedAt: item.updatedAt as string,
  }
}
