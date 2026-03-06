import { z } from "zod"
import { router, publicProcedure } from "../trpc"
import { listRegistry, getRegistry, createRegistry, updateRegistry, deleteRegistry, upsertTool } from "@/lib/db"
import { listGateways, getGatewayTools, listClients, getPolicyStatus, addClient, revokeClient, createAgentClient, getWorkloadToken, createPolicyEngine, addPolicy, deletePolicy, attachPolicy, detachPolicy, createPermitPolicy } from "@/lib/aws"

export const appRouter = router({
  gateway: router({
    list: publicProcedure.query(() => listGateways()),
    tools: publicProcedure.input(z.object({ name: z.string() })).query(({ input }) => getGatewayTools(input.name)),
    clients: publicProcedure.input(z.object({ name: z.string() })).query(({ input }) => listClients(input.name)),
    addClient: publicProcedure.input(z.object({ gateway: z.string(), clientName: z.string(), allowedTools: z.string().optional() })).mutation(({ input }) => addClient(input.gateway, input.clientName, input.allowedTools)),
    createPermitPolicy: publicProcedure.input(z.object({ gateway: z.string(), clientName: z.string(), clientId: z.string(), toolNames: z.array(z.string()) })).mutation(({ input }) => createPermitPolicy(input.gateway, input.clientName, input.clientId, input.toolNames)),
    revokeClient: publicProcedure.input(z.object({ gateway: z.string(), clientName: z.string() })).mutation(({ input }) => revokeClient(input.gateway, input.clientName)),
    createAgentClient: publicProcedure.input(z.object({ workloadName: z.string() })).mutation(({ input }) => createAgentClient(input.workloadName)),
    getWorkloadToken: publicProcedure.input(z.object({ workloadName: z.string() })).mutation(({ input }) => getWorkloadToken(input.workloadName)),
    policy: publicProcedure.input(z.object({ name: z.string() })).query(({ input }) => getPolicyStatus(input.name)),
    createPolicyEngine: publicProcedure.input(z.object({ name: z.string() })).mutation(({ input }) => createPolicyEngine(input.name)),
    addPolicy: publicProcedure.input(z.object({ engine: z.string(), name: z.string(), statement: z.string() })).mutation(({ input }) => addPolicy(input.engine, input.name, input.statement)),
    deletePolicy: publicProcedure.input(z.object({ engine: z.string(), name: z.string() })).mutation(({ input }) => deletePolicy(input.engine, input.name)),
    attachPolicy: publicProcedure.input(z.object({ engine: z.string(), gateway: z.string(), mode: z.string() })).mutation(({ input }) => attachPolicy(input.engine, input.gateway, input.mode)),
    detachPolicy: publicProcedure.input(z.object({ gateway: z.string() })).mutation(({ input }) => detachPolicy(input.gateway)),
  }),

  registry: router({
    list: publicProcedure.input(z.object({ search: z.string().optional() }).optional()).query(({ input }) =>
      listRegistry(input?.search)
    ),
    get: publicProcedure.input(z.object({ id: z.string() })).query(({ input }) =>
      getRegistry(input.id)
    ),
    create: publicProcedure.input(z.object({ name: z.string(), description: z.string().optional(), owner: z.string().optional(), repoUrl: z.string().optional(), runtimeArn: z.string().optional(), version: z.string().optional(), tags: z.array(z.string()).optional(), gatewayName: z.string().optional(), targetName: z.string().optional(), protocol: z.string().optional(), endpointUrl: z.string().optional() })).mutation(({ input }) =>
      createRegistry({ ...input, version: input.version || "1.0.0", tags: input.tags || [], protocol: input.protocol || "mcp", skills: "[]" })
    ),
    update: publicProcedure.input(z.object({ id: z.string(), data: z.object({ description: z.string().optional(), owner: z.string().optional(), repoUrl: z.string().optional(), version: z.string().optional(), tags: z.array(z.string()).optional() }) })).mutation(({ input }) =>
      updateRegistry(input.id, input.data)
    ),
    delete: publicProcedure.input(z.object({ id: z.string() })).mutation(({ input }) =>
      deleteRegistry(input.id)
    ),
    sync: publicProcedure.input(z.object({ serverId: z.string(), gatewayName: z.string() })).mutation(async ({ input }) => {
      const groups = await getGatewayTools(input.gatewayName)
      const server = await getRegistry(input.serverId)
      if (!server) throw new Error("Server not found")
      const targetTools = groups.find(g => g.target === server.targetName)?.tools || groups.flatMap(g => g.tools)
      for (const t of targetTools) {
        await upsertTool(input.serverId, { name: t.name, shortName: t.shortName, description: t.description })
      }
      return getRegistry(input.serverId)
    }),
    syncFromEndpoint: publicProcedure.input(z.object({ id: z.string(), authHeader: z.string().optional() })).mutation(async ({ input }) => {
      const server = await getRegistry(input.id)
      if (!server?.endpointUrl) throw new Error("No endpoint URL")
      const url = server.endpointUrl
      const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json, text/event-stream" }
      if (input.authHeader) headers["Authorization"] = input.authHeader
      await fetch(url, { method: "POST", headers, body: JSON.stringify({ jsonrpc: "2.0", id: "1", method: "initialize", params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "registry", version: "1.0" } } }), signal: AbortSignal.timeout(15000) })
      const toolResp = await fetch(url, { method: "POST", headers, body: JSON.stringify({ jsonrpc: "2.0", id: "2", method: "tools/list" }), signal: AbortSignal.timeout(15000) })
      const toolText = await toolResp.text()
      const dataLine = toolText.split("\n").find(l => l.startsWith("data:")) || toolText
      const parsed = JSON.parse(dataLine.replace(/^data:\s*/, ""))
      for (const t of parsed.result?.tools || []) {
        await upsertTool(input.id, { name: t.name, shortName: t.name, description: (t.description || "").slice(0, 200) })
      }
      return getRegistry(input.id)
    }),
    fetchCard: publicProcedure.input(z.object({ id: z.string() })).mutation(async ({ input }) => {
      const server = await getRegistry(input.id)
      if (!server) throw new Error("Server not found")
      const arn = server.runtimeArn || server.endpointUrl || ""
      if (!arn) throw new Error("No endpoint URL or ARN")
      let card: Record<string, unknown>
      if (arn.startsWith("arn:aws:bedrock-agentcore:")) {
        const { exec } = await import("child_process")
        const { promisify } = await import("util")
        const execAsync = promisify(exec)
        const region = process.env.GATEWAY_REGION || "us-east-1"
        const py = `import json,boto3,requests,uuid\nfrom urllib.parse import quote\nfrom botocore.auth import SigV4Auth\nfrom botocore.awsrequest import AWSRequest\nsession=boto3.Session(region_name="${region}")\ncreds=session.get_credentials().get_frozen_credentials()\nescaped=quote("${arn}",safe="")\nurl=f"https://bedrock-agentcore.${region}.amazonaws.com/runtimes/{escaped}/invocations/.well-known/agent-card.json"\nreq=AWSRequest(method="GET",url=url,headers={"Accept":"application/json","X-Amzn-Bedrock-AgentCore-Runtime-Session-Id":f"registry-session-{uuid.uuid4().hex}"})\nSigV4Auth(creds,"bedrock-agentcore","${region}").add_auth(req)\nr=requests.get(url,headers=dict(req.headers),timeout=15)\nr.raise_for_status()\nprint(json.dumps(r.json()))`
        const { stdout } = await execAsync(`python3 -c '${py.replace(/'/g, "'\\''")}'`, { timeout: 20000, env: { ...process.env, SSL_CERT_FILE: "", REQUESTS_CA_BUNDLE: "" } })
        card = JSON.parse(stdout.trim())
      } else {
        const cardUrl = arn.endsWith("agent-card.json") ? arn : `${arn.replace(/\/$/, "")}/.well-known/agent-card.json`
        const resp = await fetch(cardUrl, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(15000) })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        card = await resp.json()
      }
      const skills = JSON.stringify(card.skills || [])
      await updateRegistry(input.id, { agentCard: JSON.stringify(card), skills, description: server.description || (card.description as string), version: (card.version as string) || server.version })
      return { ...card, _serverId: input.id }
    }),
  }),

  access: router({
    list: publicProcedure.query(() => [] as unknown[]),
    create: publicProcedure.input(z.object({ requester: z.string(), serverId: z.string(), toolNames: z.array(z.string()).optional() })).mutation(() => ({})),
    resolve: publicProcedure.input(z.object({ id: z.string(), status: z.enum(["APPROVED", "DENIED"]), approver: z.string() })).mutation(() => ({})),
  }),
})

export type AppRouter = typeof appRouter
