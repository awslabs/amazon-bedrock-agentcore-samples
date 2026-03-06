import { exec } from "child_process"
import { promisify } from "util"
import { BedrockAgentCoreControlClient, ListGatewaysCommand, GetGatewayCommand } from "@aws-sdk/client-bedrock-agentcore-control"
import { CognitoIdentityProviderClient, ListUserPoolClientsCommand, DescribeUserPoolClientCommand } from "@aws-sdk/client-cognito-identity-provider"
import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager"
import type { Gateway, ToolGroup, Client, PolicyStatus } from "./types"

const execAsync = promisify(exec)
const REGION = process.env.GATEWAY_REGION || "us-east-1"
const CACHE_TTL = 30_000

const agentCoreControl = new BedrockAgentCoreControlClient({ region: REGION })
const cognito = new CognitoIdentityProviderClient({ region: REGION })
const secrets = new SecretsManagerClient({ region: REGION })

const cache = new Map<string, { data: unknown; ts: number }>()

function cached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const hit = cache.get(key)
  if (hit && Date.now() - hit.ts < CACHE_TTL) return Promise.resolve(hit.data as T)
  return fn().then(data => { cache.set(key, { data, ts: Date.now() }); return data })
}

async function run(cmd: string): Promise<string> {
  try {
    const { stdout } = await execAsync(cmd, { encoding: "utf-8", timeout: 30000, env: { ...process.env, SSL_CERT_FILE: "", REQUESTS_CA_BUNDLE: "" } })
    return stdout.trim()
  } catch {
    return ""
  }
}

async function getSecret(secretId: string): Promise<Record<string, string> | null> {
  try {
    const resp = await secrets.send(new GetSecretValueCommand({ SecretId: secretId }))
    return resp.SecretString ? JSON.parse(resp.SecretString) : null
  } catch {
    return null
  }
}

async function getGatewayToken(gatewayName: string): Promise<string> {
  return cached(`token:${gatewayName}`, async () => {
    const creds = await getSecret(`${gatewayName}-mcp-cognito-credentials`)
    if (!creds) throw new Error(`No credentials for ${gatewayName}`)
    const resp = await fetch(`https://${creds.domain}/oauth2/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "client_credentials",
        client_id: creds.client_id,
        client_secret: creds.client_secret,
        scope: creds.scope,
      }),
    })
    const data = await resp.json()
    return data.access_token
  })
}

// --- Gateway list (direct AWS SDK) ---

export function listGateways(): Promise<Gateway[]> {
  return cached("gateways", async () => {
    const resp = await agentCoreControl.send(new ListGatewaysCommand({}))
    const gateways = await Promise.all((resp.items || []).map(async gw => {
      let idp = "Cognito"
      try {
        const detail = await agentCoreControl.send(new GetGatewayCommand({ gatewayIdentifier: gw.gatewayId }))
        const url = ((detail as unknown as Record<string, Record<string, Record<string, string>>>).authorizerConfiguration?.customJWTAuthorizer?.discoveryUrl) || ""
        if (url.includes("microsoftonline")) idp = "EntraID"
        else if (url.includes("cognito")) idp = "Cognito"
        else if (url) idp = "Custom"
      } catch {}
      return { name: gw.name || "", id: gw.gatewayId || "", status: gw.status || "", protocol: gw.protocolType || "", idp }
    }))
    return gateways
  })
}

// --- Tools (direct MCP HTTP call) ---

export function getGatewayTools(name: string): Promise<ToolGroup[]> {
  return cached(`tools:${name}`, async () => {
    try {
      const [token, gwResp] = await Promise.all([
        getGatewayToken(name),
        agentCoreControl.send(new ListGatewaysCommand({}))
      ])
      
      const gateway = gwResp.items?.find(gw => gw.name === name)
      if (!gateway?.gatewayId) throw new Error("Gateway not found")
      
      const gwDetail = await agentCoreControl.send(new GetGatewayCommand({ gatewayIdentifier: gateway.gatewayId }))
      const gatewayUrl = gwDetail.gatewayUrl
      if (!gatewayUrl) throw new Error("No gateway URL")
      
      return await fetchToolsViaMcp(gatewayUrl, token)
    } catch {
      // Fallback to CLI
      const out = await run(`gatewayctl gateway tools --name ${name} --region ${REGION}`)
      return parseToolsOutput(out)
    }
  })
}

async function fetchToolsViaMcp(gatewayUrl: string, token: string): Promise<ToolGroup[]> {
  const allTools: Array<{ name: string; description?: string }> = []
  let cursor: string | undefined

  do {
    const payload: Record<string, unknown> = { jsonrpc: "2.0", id: "list-tools", method: "tools/list" }
    if (cursor) payload.params = { cursor }

    const resp = await fetch(gatewayUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    })
    const data = await resp.json()
    if (data.error) throw new Error(data.error.message)
    const result = data.result || {}
    allTools.push(...(result.tools || []))
    cursor = result.nextCursor
  } while (cursor)

  // Group by target (target___toolName convention)
  const groups = new Map<string, ToolGroup>()
  for (const tool of allTools) {
    const [target, shortName] = tool.name.includes("___") ? tool.name.split("___", 2) : ["(gateway)", tool.name]
    if (!groups.has(target)) groups.set(target, { target, tools: [] })
    groups.get(target)!.tools.push({ name: tool.name, shortName, description: (tool.description || "").split("\n")[0].slice(0, 100) })
  }
  return Array.from(groups.values())
}

function parseToolsOutput(out: string): ToolGroup[] {
  if (!out) return []
  const groups: ToolGroup[] = []
  let current: ToolGroup | null = null
  for (const line of out.split("\n")) {
    const targetMatch = line.match(/[┌─]+\s+(\S+)\s+\(/)
    if (targetMatch) { current = { target: targetMatch[1], tools: [] }; groups.push(current); continue }
    const toolMatch = line.match(/[├└]──\s+(\S+):\s+(.*)/)
    if (toolMatch && current) {
      current.tools.push({ name: `${current.target}___${toolMatch[1]}`, shortName: toolMatch[1], description: toolMatch[2].trim() })
    }
  }
  return groups
}

// --- Clients (direct AWS SDK) ---

export function listClients(name: string): Promise<Client[]> {
  return cached(`clients:${name}`, async () => {
    const creds = await getSecret(`${name}-mcp-cognito-credentials`)
    if (!creds?.pool_id) return []

    // Get allowed client IDs from gateway config
    const gwResp = await agentCoreControl.send(new ListGatewaysCommand({}))
    const gateway = gwResp.items?.find(gw => gw.name === name)
    if (!gateway?.gatewayId) return []
    
    const gwDetail = await agentCoreControl.send(new GetGatewayCommand({ gatewayIdentifier: gateway.gatewayId }))
    const allowedIds = new Set(gwDetail.authorizerConfiguration?.customJWTAuthorizer?.allowedClients || [])

    // List Cognito clients directly via SDK
    const clients: Client[] = []
    let nextToken: string | undefined
    do {
      const resp = await cognito.send(new ListUserPoolClientsCommand({
        UserPoolId: creds.pool_id,
        MaxResults: 60,
        NextToken: nextToken,
      }))
      for (const c of resp.UserPoolClients || []) {
        const detail = await cognito.send(new DescribeUserPoolClientCommand({
          UserPoolId: creds.pool_id,
          ClientId: c.ClientId!,
        }))
        const uc = detail.UserPoolClient!
        clients.push({
          name: uc.ClientName || "",
          clientId: uc.ClientId || "",
          allowed: allowedIds.has(uc.ClientId || ""),
          createdAt: uc.CreationDate?.toISOString(),
          lastModified: uc.LastModifiedDate?.toISOString(),
          scopes: uc.AllowedOAuthScopes,
        })
      }
      nextToken = resp.NextToken
    } while (nextToken)

    return clients
  })
}

// --- Policy (still CLI for now) ---

function parsePolicy(out: string): PolicyStatus | null {
  if (!out || out.includes("No policy engine")) return null
  const arnMatch = out.match(/Policy Engine ARN:\s+(\S+)/)
  const modeMatch = out.match(/Enforcement Mode:\s+(\S+)/)
  const policies: { name: string; status: string }[] = []
  for (const line of out.split("\n")) {
    const m = line.match(/•\s+(\S+)\s+\((\w+)\)/)
    if (m) policies.push({ name: m[1], status: m[2] })
  }
  return { engineArn: arnMatch?.[1] || "", mode: modeMatch?.[1] || "", policies }
}

export function getPolicyStatus(name: string): Promise<PolicyStatus | null> {
  return cached(`policy:${name}`, () => run(`gatewayctl policy status --gateway ${name} --region ${REGION}`).then(parsePolicy))
}

// --- Mutations ---

export async function addClient(gateway: string, clientName: string, allowedTools?: string): Promise<string> {
  cache.delete(`clients:${gateway}`)
  if (allowedTools) {
    // Use permit-only pattern: create client without tool restrictions via CLI,
    // then create a permit-only Cedar policy separately
    const result = await run(`gatewayctl gateway add-client --name ${gateway} --client-name ${clientName} --region ${REGION}`)
    return result
  }
  return run(`gatewayctl gateway add-client --name ${gateway} --client-name ${clientName} --region ${REGION}`)
}

export async function createPermitPolicy(gateway: string, clientName: string, clientId: string, toolNames: string[]): Promise<string> {
  // Generate permit-only Cedar policy for tool composition
  // This controls both tools/list (discovery) and tools/call (execution)
  const actions = toolNames.map(t => `AgentCore::Action::"${t}"`).join(",\n    ")
  const gatewayArn = await getGatewayArn(gateway)
  const cedar = `permit(\n  principal is AgentCore::OAuthUser,\n  action in [\n    ${actions}\n  ],\n  resource == AgentCore::Gateway::"${gatewayArn}"\n)\nwhen {\n  principal.hasTag("client_id") &&\n  principal.getTag("client_id") == "${clientId}"\n};`
  const safeName = clientName.replace(/-/g, "_")
  const policyName = `team_${safeName}_tools`
  return run(`gatewayctl policy add --engine $(gatewayctl policy status --gateway ${gateway} --region ${REGION} 2>/dev/null | grep -o '[^ ]*policy-engine[^ ]*' | head -1) --name ${policyName} --statement '${cedar.replace(/'/g, "'\\''")}' --validation-mode IGNORE_ALL_FINDINGS --region ${REGION}`)
}

async function getGatewayArn(gateway: string): Promise<string> {
  try {
    const resp = await agentCoreControl.send(new ListGatewaysCommand({}))
    const gw = resp.items?.find(g => g.name === gateway)
    if (!gw?.gatewayId) return ""
    const detail = await agentCoreControl.send(new GetGatewayCommand({ gatewayIdentifier: gw.gatewayId }))
    return (detail as unknown as Record<string, string>).gatewayArn || ""
  } catch { return "" }
}

export async function revokeClient(gateway: string, clientName: string): Promise<string> {
  cache.delete(`clients:${gateway}`)
  return run(`echo y | gatewayctl gateway revoke-client --name ${gateway} --client-name ${clientName} --region ${REGION}`)
}

export async function createAgentClient(workloadName: string): Promise<{ name: string; arn: string }> {
  const { exec } = await import("child_process")
  const { promisify } = await import("util")
  const execAsync = promisify(exec)
  const py = `
import boto3, json
client = boto3.client('bedrock-agentcore-control', region_name='${REGION}')
try:
    resp = client.get_workload_identity(name='${workloadName}')
    print(json.dumps({"name": resp["name"], "arn": resp["workloadIdentityArn"], "exists": True}))
except:
    resp = client.create_workload_identity(name='${workloadName}')
    print(json.dumps({"name": resp["name"], "arn": resp["workloadIdentityArn"], "exists": False}))
`
  const { stdout } = await execAsync(`python3 -c '${py.replace(/'/g, "'\\''")}'`, { timeout: 15000, env: { ...process.env, SSL_CERT_FILE: "", REQUESTS_CA_BUNDLE: "" } })
  return JSON.parse(stdout.trim())
}

export async function getWorkloadToken(workloadName: string): Promise<string> {
  const { exec } = await import("child_process")
  const { promisify } = await import("util")
  const execAsync = promisify(exec)
  const py = `
import boto3, json
client = boto3.client('bedrock-agentcore', region_name='${REGION}')
resp = client.get_workload_access_token(workloadName='${workloadName}')
print(resp.get('accessToken', ''))
`
  const { stdout } = await execAsync(`python3 -c '${py.replace(/'/g, "'\\''")}'`, { timeout: 15000, env: { ...process.env, SSL_CERT_FILE: "", REQUESTS_CA_BUNDLE: "" } })
  return stdout.trim()
}

export async function createPolicyEngine(name: string): Promise<string> {
  return run(`gatewayctl policy create-engine --name ${name} --region ${REGION}`)
}

export async function addPolicy(engine: string, name: string, statement: string): Promise<string> {
  return run(`gatewayctl policy add --engine ${engine} --name ${name} --statement '${statement.replace(/'/g, "'\\''")}' --region ${REGION}`)
}

export async function deletePolicy(engine: string, name: string): Promise<string> {
  return run(`gatewayctl policy delete --engine ${engine} --name ${name} --region ${REGION}`)
}

export async function attachPolicy(engine: string, gateway: string, mode: string): Promise<string> {
  return run(`gatewayctl policy attach --engine ${engine} --gateway ${gateway} --mode ${mode} --region ${REGION}`)
}

export async function detachPolicy(gateway: string): Promise<string> {
  return run(`gatewayctl policy detach --gateway ${gateway} --region ${REGION}`)
}

export async function getToken(gateway: string, client?: string): Promise<string> {
  if (!client) {
    return getGatewayToken(gateway)
  }
  const clientFlag = ` --client ${client}`
  const out = await run(`gatewayctl gateway get-token --name ${gateway}${clientFlag} --region ${REGION}`)
  return out.split("\n").filter(l => l.trim() && !l.startsWith("Fetching") && !l.startsWith("⚠")).join("\n").trim()
}
