"use client"

import { useEffect, useState } from "react"
import { LayoutDashboard, Wrench, Users, Shield, Search, Plus, ChevronDown, ChevronRight, X, Package } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { RegistryPage } from "@/components/registry-page"
import type { Gateway, ToolGroup, Client, PolicyStatus } from "@/lib/types"

const GW_NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "clients", label: "Clients & Access", icon: Users },
  { id: "policies", label: "Policies", icon: Shield },
]

export default function Dashboard() {
  const [gateways, setGateways] = useState<Gateway[]>([])
  const [selected, setSelected] = useState("")
  const [page, setPage] = useState("registry")
  const [tools, setTools] = useState<ToolGroup[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [policy, setPolicy] = useState<PolicyStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [gwExpanded, setGwExpanded] = useState(true)

  const isGwPage = GW_NAV.some(n => n.id === page)

  useEffect(() => {
    fetch("/api/gateways").then(r => r.json()).then(data => {
      setGateways(data)
      if (data.length) setSelected(data[0].name)
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selected) return
    Promise.all([
      fetch(`/api/tools?gateway=${selected}`).then(r => r.json()),
      fetch(`/api/clients?gateway=${selected}`).then(r => r.json()),
      fetch(`/api/policies?gateway=${selected}`).then(r => r.json()),
    ]).then(([t, c, p]) => { setTools(t); setClients(c); setPolicy(p) })
  }, [selected])

  const gw = gateways.find(g => g.name === selected)
  const totalTools = tools.reduce((n, g) => n + g.tools.length, 0)

  if (loading) return <div className="flex h-screen items-center justify-center text-zinc-400">Loading...</div>

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <div className="w-64 bg-zinc-900 text-white flex flex-col shrink-0">
        <div className="p-5 border-b border-zinc-800">
          <h1 className="text-lg font-bold">🚀 GatewayCTL</h1>
          <p className="text-xs text-zinc-400 mt-1">Platform</p>
        </div>

        <nav className="flex-1 p-2 space-y-1 overflow-auto">
          {/* Registry — standalone */}
          <button
            onClick={() => setPage("registry")}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              page === "registry" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
            }`}
          >
            <Package size={18} />
            Registry
          </button>

          {/* Gateway section */}
          <div className="pt-3">
            <button
              onClick={() => setGwExpanded(e => !e)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300"
            >
              {gwExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              Gateway
            </button>

            {gwExpanded && (
              <>
                <div className="px-2 py-1.5">
                  <select
                    value={selected}
                    onChange={e => { setSelected(e.target.value); if (!isGwPage) setPage("overview") }}
                    className="w-full bg-zinc-800 text-sm rounded-lg px-3 py-2 border border-zinc-700 focus:outline-none focus:border-zinc-500"
                  >
                    {gateways.map(g => (
                      <option key={g.name} value={g.name}>{g.name}</option>
                    ))}
                  </select>
                </div>

                {GW_NAV.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setPage(item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      page === item.id ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
                    }`}
                  >
                    <item.icon size={16} />
                    {item.label}
                  </button>
                ))}
              </>
            )}
          </div>
        </nav>

        <div className="p-4 border-t border-zinc-800 text-xs text-zinc-500">
          {gw && <>{gw.id}<br/>{gw.status}</>}
          <form action="/api/auth/signout" method="POST" className="mt-2">
            <button type="submit" className="text-zinc-500 hover:text-white text-xs">Sign out</button>
          </form>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 overflow-auto p-8">
        {page === "registry" && <RegistryPage />}
        {page === "overview" && <OverviewPage gw={gw} tools={tools} totalTools={totalTools} clients={clients} policy={policy} />}
        {page === "tools" && <ToolsPage tools={tools} />}
        {page === "clients" && <ClientsPage clients={clients} tools={tools} gateway={selected} gatewayId={gw?.id || ""} idp={gw?.idp || "Cognito"} onRefresh={() => fetch(`/api/clients?gateway=${selected}`).then(r => r.json()).then(setClients)} />}
        {page === "policies" && <PoliciesPage policy={policy} gateway={selected} />}
      </div>
    </div>
  )
}

function OverviewPage({ gw, tools, totalTools, clients, policy }: { gw?: Gateway; tools: ToolGroup[]; totalTools: number; clients: Client[]; policy: PolicyStatus | null }) {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Overview</h2>
      <div className="grid grid-cols-4 gap-4 mb-8">
        <MetricCard label="Targets" value={tools.length} />
        <MetricCard label="Tools" value={totalTools} />
        <MetricCard label="Clients" value={clients.length} />
        <MetricCard label="Policy" value={policy?.mode || "None"} />
      </div>
      {gw && (
        <Card>
          <CardHeader><CardTitle>Gateway Details</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-zinc-500">Name</span><p className="font-medium">{gw.name}</p></div>
              <div><span className="text-zinc-500">ID</span><p className="font-mono text-xs">{gw.id}</p></div>
              <div><span className="text-zinc-500">Status</span><span className="block"><Badge variant={gw.status === "READY" ? "success" : "secondary"}>{gw.status}</Badge></span></div>
              <div><span className="text-zinc-500">Protocol</span><p>{gw.protocol}</p></div>
              <div><span className="text-zinc-500">Identity Provider</span><span className="block"><Badge variant={gw.idp === "EntraID" ? "secondary" : "outline"}>{gw.idp || "Cognito"}</Badge></span></div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="p-6">
        <p className="text-sm text-zinc-500">{label}</p>
        <p className="text-3xl font-bold mt-1">{value}</p>
      </CardContent>
    </Card>
  )
}

function ToolsPage({ tools }: { tools: ToolGroup[] }) {
  const [search, setSearch] = useState("")
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Tools Registry</h2>
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search tools..."
          className="w-full pl-10 pr-4 py-2.5 rounded-lg border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      {tools.map(group => {
        const filtered = group.tools.filter(t =>
          !search || t.shortName.toLowerCase().includes(search.toLowerCase()) || t.description.toLowerCase().includes(search.toLowerCase())
        )
        if (!filtered.length) return null
        const isOpen = expanded[group.target] ?? !search
        return (
          <div key={group.target} className="mb-4">
            <button
              onClick={() => setExpanded(p => ({ ...p, [group.target]: !isOpen }))}
              className="w-full flex items-center gap-2 p-3 rounded-lg bg-white border hover:bg-zinc-50 text-left"
            >
              {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span className="font-semibold">{group.target}</span>
              <Badge variant="secondary" className="ml-2">{filtered.length} tools</Badge>
            </button>
            {isOpen && (
              <div className="mt-1 ml-6 space-y-1">
                {filtered.map(t => (
                  <div key={t.name} className="p-3 rounded-lg border bg-white">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="font-semibold text-sm">{t.shortName}</span>
                        <p className="text-sm text-zinc-500 mt-0.5">{t.description}</p>
                      </div>
                    </div>
                    <code className="text-[11px] text-zinc-400 mt-1 block">{t.name}</code>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ClientsPage({ clients, tools, gateway, gatewayId, idp, onRefresh }: { clients: Client[]; tools: ToolGroup[]; gateway: string; gatewayId: string; idp: string; onRefresh: () => void }) {
  const [showForm, setShowForm] = useState(false)
  const [clientType, setClientType] = useState<"team" | "agent">("team")
  const [name, setName] = useState("")
  const [workloadName, setWorkloadName] = useState("")
  const [restrict, setRestrict] = useState(false)
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [revoking, setRevoking] = useState<string | null>(null)
  const [revokePending, setRevokePending] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [result, setResult] = useState<{ message: string; detail?: string } | null>(null)
  const allTools = tools.flatMap(g => g.tools)

  const resetForm = () => { setShowForm(false); setName(""); setWorkloadName(""); setRestrict(false); setSelectedTools([]); setSubmitting(false); setResult(null); setClientType("team") }

  const handleSubmit = async () => {
    setSubmitting(true)
    const toolsParam = restrict ? selectedTools.join(",") : undefined
    try {
      if (clientType === "agent") {
        const resp = await fetch("/api/clients", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ gateway, clientName: workloadName, type: "agent", workloadName, allowedTools: toolsParam }) })
        const data = await resp.json()
        setResult({ message: "✅ Agent client created", detail: `Workload: ${workloadName}\n${data.workload ? `ARN: ${data.workload.arn}\n` : ""}Auth: ${idp} + AgentCore Identity\nAgent gets tokens via: GetWorkloadAccessToken(workloadName="${workloadName}")` })
      } else {
        await fetch("/api/clients", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ gateway, clientName: name, allowedTools: toolsParam }) })
        setResult({ message: `✅ Team client "${name}" created`, detail: `Auth: ${idp}\nGet token: gatewayctl gateway get-token --name ${gateway} --client ${name}` })
      }
    } catch {}
    setSubmitting(false); onRefresh()
  }

  const handleRevoke = async (clientName: string) => {
    setRevokePending(true)
    // Strip gateway prefix — CLI expects short name (e.g., "dev-alice" not "mcp-gateway-dev-alice")
    const shortName = clientName.replace(`${gateway}-`, "")
    await fetch("/api/clients", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ gateway, clientName: shortName }) })
    setRevoking(null); setRevokePending(false); onRefresh()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Clients & Access</h2>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800"><Plus size={16} /> Add Client</button>
      </div>

      {showForm && (
        <Card className="mb-6">
          <CardHeader><div className="flex items-center justify-between"><CardTitle>New Client</CardTitle><button onClick={resetForm}><X size={18} className="text-zinc-400" /></button></div></CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex gap-2 mb-2">
                <button onClick={() => setClientType("team")} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${clientType === "team" ? "border-zinc-900 bg-zinc-900 text-white" : "hover:bg-zinc-50"}`}><Users size={14} /> Team / User</button>
                <button onClick={() => setClientType("agent")} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${clientType === "agent" ? "border-zinc-900 bg-zinc-900 text-white" : "hover:bg-zinc-50"}`}><Package size={14} /> Agent</button>
              </div>

              <p className="text-xs text-zinc-400">
                Gateway IdP: <span className="font-medium text-zinc-600">{idp}</span>
                {clientType === "team" ? ` — client authenticates via ${idp}` : ` — agent uses AgentCore Identity (backed by ${idp})`}
              </p>

              {clientType === "team" && (
                <input value={name} onChange={e => setName(e.target.value)} placeholder="Client name (e.g., team-frontend, dev-alice)" className="w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
              )}

              {clientType === "agent" && (
                <input value={workloadName} onChange={e => setWorkloadName(e.target.value)} placeholder="Workload name (e.g., orchestrator-agent)" className="w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
              )}

              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={restrict} onChange={e => setRestrict(e.target.checked)} className="rounded" /> Compose tool access (Cedar permit-only)</label>
              {restrict && (<><p className="text-xs text-amber-600">⚡ Creates a Cedar permit-only policy. The client will only discover and invoke the selected tools. All other tools are invisible (default deny). Policy engine must be in ENFORCE mode.</p><div className="max-h-48 overflow-auto border rounded-lg p-2 space-y-1">{allTools.map(t => (<label key={t.name} className="flex items-center gap-2 text-sm p-1 hover:bg-zinc-50 rounded"><input type="checkbox" checked={selectedTools.includes(t.name)} onChange={e => setSelectedTools(prev => e.target.checked ? [...prev, t.name] : prev.filter(n => n !== t.name))} className="rounded" />{t.shortName} <span className="text-zinc-400 text-xs">({t.name.split("___")[0]})</span></label>))}</div></>)}

              {result && (<div className="p-3 rounded-lg bg-green-50 border border-green-200 text-sm"><p className="font-medium text-green-800">{result.message}</p>{result.detail && <pre className="text-xs text-green-700 mt-1 whitespace-pre-wrap">{result.detail}</pre>}</div>)}

              <button onClick={handleSubmit} disabled={submitting || (clientType === "team" ? !name : !workloadName)} className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800 disabled:opacity-50">
                {submitting ? "Creating..." : `Create ${clientType === "team" ? "Team" : "Agent"} Client`}
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-zinc-500"><th className="p-4">Name</th><th className="p-4">Client ID</th><th className="p-4">Status</th><th className="p-4 text-right">Actions</th></tr></thead>
            <tbody>
              {clients.map(c => {
                const isOpen = expanded === c.clientId
                const isAgent = c.name.includes("agentforce") || c.name.includes("agent") || c.name.includes("orchestrator")
                return (
                  <tr key={c.clientId} className={`border-b last:border-0 ${revoking === c.name ? "bg-red-50" : isOpen ? "bg-zinc-50" : "hover:bg-zinc-50"}`}>
                    <td colSpan={4} className="p-0">
                      <div className="flex items-center p-4 cursor-pointer" onClick={() => setExpanded(isOpen ? null : c.clientId)}>
                        <div className="flex-1">
                          <span className="font-medium">{c.name}</span>
                          {isAgent && <Badge className="ml-2 bg-purple-100 text-purple-700 text-[10px]">Agent</Badge>}
                        </div>
                        <span className="font-mono text-xs text-zinc-500 w-72 truncate">{c.clientId}</span>
                        <span className="w-24 text-center"><Badge variant={c.allowed ? "success" : "destructive"}>{c.allowed ? "Allowed" : "Denied"}</Badge></span>
                        <span className="w-24 text-right">
                          {revoking === c.name ? (<span className="flex items-center justify-end gap-1"><button onClick={e => { e.stopPropagation(); handleRevoke(c.name) }} disabled={revokePending} className="px-2 py-1 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">{revokePending ? "..." : "Revoke"}</button><button onClick={e => { e.stopPropagation(); setRevoking(null) }} className="px-2 py-1 text-xs border rounded-lg hover:bg-zinc-50">Cancel</button></span>) : (<button onClick={e => { e.stopPropagation(); setRevoking(c.name) }} className="text-xs text-zinc-400 hover:text-red-600">Revoke</button>)}
                        </span>
                      </div>
                      {isOpen && (
                        <div className="px-4 pb-4 space-y-3">
                          <div className="grid grid-cols-3 gap-4 p-3 rounded-lg bg-white border text-xs">
                            <div><span className="text-zinc-400 block">Client ID</span><span className="font-mono break-all">{c.clientId}</span></div>
                            <div><span className="text-zinc-400 block">Created</span><span>{c.createdAt ? new Date(c.createdAt).toLocaleDateString() : "—"}</span></div>
                            <div><span className="text-zinc-400 block">Last Modified</span><span>{c.lastModified ? new Date(c.lastModified).toLocaleDateString() : "—"}</span></div>
                            <div><span className="text-zinc-400 block">Auth Type</span><span>{idp}</span></div>
                            <div><span className="text-zinc-400 block">OAuth Scopes</span><span>{c.scopes?.join(", ") || "—"}</span></div>
                            <div><span className="text-zinc-400 block">Type</span><span>{isAgent ? "Agent (Identity)" : "Team / User"}</span></div>
                          </div>
                          <div className="p-3 rounded-lg bg-white border text-xs">
                            <span className="text-zinc-400 block mb-2">Registry agents using this client</span>
                            {(() => {
                              const shortName = c.name.replace(`${gateway}-`, "")
                              return (<p className="text-zinc-500">Agents with gateway <span className="font-medium">{gateway}</span> and matching client name will appear here. Check the Registry for entries targeting this gateway.</p>)
                            })()}
                          </div>
                          <div className="p-3 rounded-lg bg-zinc-100 border text-xs font-mono">
                            <span className="text-zinc-400 block mb-1">Get token</span>
                            gatewayctl gateway get-token --name {gateway} --client {c.name.replace(`${gateway}-`, "")}
                          </div>
                          <div className="p-3 rounded-lg bg-zinc-900 text-green-400 border text-xs font-mono overflow-auto">
                            <span className="text-zinc-500 block mb-2"># Connect from an agent on AgentCore Runtime</span>
                            {isAgent ? (
                              <pre className="whitespace-pre-wrap">{`import boto3, requests, json

# 1. Get token via AgentCore Identity
identity = boto3.client("bedrock-agentcore", region_name="${process.env.GATEWAY_REGION || "us-east-1"}")
token = identity.get_workload_access_token(
    workloadName="${c.name.replace(`${gateway}-`, "")}"
)["accessToken"]

# 2. Gateway URL
gateway_url = "https://${gatewayId}.gateway.bedrock-agentcore.${process.env.GATEWAY_REGION || "us-east-1"}.amazonaws.com/mcp"

# 3. List available tools (filtered by Cedar policy)
resp = requests.post(gateway_url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"jsonrpc": "2.0", "id": "1", "method": "tools/list"})
tools = resp.json()["result"]["tools"]
print(f"Available tools: {[t['name'] for t in tools]}")

# 4. Call a tool
resp = requests.post(gateway_url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"jsonrpc": "2.0", "id": "2", "method": "tools/call",
          "params": {"name": "<target___tool_name>", "arguments": {}}})
print(resp.json())`}</pre>
                            ) : (
                              <pre className="whitespace-pre-wrap">{`import subprocess, requests, json

# 1. Get token via CLI
token = subprocess.run(
    ["gatewayctl", "gateway", "get-token", "--name", "${gateway}",
     "--client", "${c.name.replace(`${gateway}-`, "")}", "--region", "${process.env.GATEWAY_REGION || "us-east-1"}"],
    capture_output=True, text=True
).stdout.strip()

# 2. Gateway URL
gateway_url = "https://${gatewayId}.gateway.bedrock-agentcore.${process.env.GATEWAY_REGION || "us-east-1"}.amazonaws.com/mcp"

# 3. List available tools (filtered by Cedar policy)
resp = requests.post(gateway_url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"jsonrpc": "2.0", "id": "1", "method": "tools/list"})
tools = resp.json()["result"]["tools"]
print(f"Available tools: {[t['name'] for t in tools]}")

# 4. Call a tool
resp = requests.post(gateway_url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"jsonrpc": "2.0", "id": "2", "method": "tools/call",
          "params": {"name": "<target___tool_name>", "arguments": {}}})
print(resp.json())`}</pre>
                            )}
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
              {!clients.length && <tr><td colSpan={4} className="p-8 text-center text-zinc-400">No clients configured</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}

function PoliciesPage({ policy, gateway }: { policy: PolicyStatus | null; gateway: string }) {
  const [showCreate, setShowCreate] = useState(false)
  const [engineName, setEngineName] = useState(() => {
    if (policy?.engineArn) {
      const parts = policy.engineArn.split("/")
      const full = parts[parts.length - 1] || ""
      return full.replace(/-[a-z0-9]+$/, "") // strip random suffix
    }
    return gateway.replace(/-/g, "_") + "_policies"
  })
  const [policyName, setPolicyName] = useState("")
  const [statement, setStatement] = useState("")
  const [mode, setMode] = useState("LOG_ONLY")
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [deletePending, setDeletePending] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = () => setRefreshKey(k => k + 1)

  const handleCreateEngine = async () => {
    setSubmitting(true)
    await fetch("/api/policies", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "create-engine", name: engineName, gateway }) })
    setSubmitting(false)
    window.location.reload()
  }

  const handleAddPolicy = async () => {
    if (!policyName || !statement) return
    setSubmitting(true)
    await fetch("/api/policies", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "add-policy", engine: engineName, name: policyName, statement, gateway }) })
    setPolicyName("")
    setStatement("")
    setShowCreate(false)
    setSubmitting(false)
    window.location.reload()
  }

  const handleDelete = async (name: string) => {
    setDeletePending(true)
    await fetch("/api/policies", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete-policy", engine: engineName, name, gateway }) })
    setDeleting(null)
    setDeletePending(false)
    window.location.reload()
  }

  const handleModeChange = async (newMode: string) => {
    setSubmitting(true)
    await fetch("/api/policies", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "attach", engine: engineName, gateway, mode: newMode }) })
    setMode(newMode)
    setSubmitting(false)
    window.location.reload()
  }

  const handleDetach = async () => {
    setSubmitting(true)
    await fetch("/api/policies", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "detach", gateway }) })
    setSubmitting(false)
    window.location.reload()
  }

  if (!policy) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Policies</h2>
        <Card>
          <CardContent className="p-8 text-center">
            <Shield className="mx-auto mb-4 text-zinc-300" size={48} />
            <p className="text-zinc-500 mb-4">No policy engine attached to this gateway.</p>
            <div className="flex items-center justify-center gap-2">
              <input value={engineName} onChange={e => setEngineName(e.target.value)} className="px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300 w-64" placeholder="Engine name" />
              <button onClick={handleCreateEngine} disabled={submitting || !engineName} className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800 disabled:opacity-50">
                {submitting ? "Creating..." : "Create & Attach Engine"}
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Policies</h2>
        <div className="flex gap-2">
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800">
            <Plus size={16} /> Add Policy
          </button>
          <button onClick={handleDetach} disabled={submitting} className="px-4 py-2 border text-sm rounded-lg hover:bg-red-50 text-red-600 disabled:opacity-50">
            Detach Engine
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-zinc-500 mb-2">Enforcement Mode</p>
            <div className="flex gap-2">
              {["LOG_ONLY", "ENFORCE"].map(m => (
                <button key={m} onClick={() => handleModeChange(m)} disabled={submitting || policy.mode === m} className={`px-3 py-1.5 rounded-lg text-sm ${policy.mode === m ? "bg-zinc-900 text-white" : "border hover:bg-zinc-50"} disabled:opacity-50`}>
                  {m}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-zinc-500">Active Policies</p>
            <p className="text-3xl font-bold mt-1">{policy.policies.length}</p>
          </CardContent>
        </Card>
      </div>

      {showCreate && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Add Cedar Policy</CardTitle>
              <button onClick={() => setShowCreate(false)}><X size={18} className="text-zinc-400" /></button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <input value={policyName} onChange={e => setPolicyName(e.target.value)} placeholder="Policy name (e.g., no-destroy)" className="w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
              <textarea value={statement} onChange={e => setStatement(e.target.value)} placeholder={'permit(\n  principal is AgentCore::OAuthUser,\n  action in [\n    AgentCore::Action::"target___tool_name"\n  ],\n  resource == AgentCore::Gateway::"<gateway-arn>"\n)\nwhen {\n  principal.hasTag("client_id") &&\n  principal.getTag("client_id") == "<client-id>"\n};'} rows={8} className="w-full px-3 py-2 rounded-lg border text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-300" />
              <button onClick={handleAddPolicy} disabled={!policyName || !statement || submitting} className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800 disabled:opacity-50">
                {submitting ? "Adding..." : "Add Policy"}
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Policies</CardTitle></CardHeader>
        <CardContent>
          {policy.policies.map(p => (
            <div key={p.name} className={`flex items-center justify-between py-3 border-b last:border-0 ${deleting === p.name ? "bg-red-50" : ""}`}>
              <div>
                <span className="font-medium text-sm">{p.name}</span>
                <Badge variant={p.status === "ACTIVE" ? "success" : "secondary"} className="ml-2">{p.status}</Badge>
                {(p.name.startsWith("client_") || p.name.startsWith("team_") || p.name === "default_permit_all") && <Badge variant="outline" className="ml-1 text-[10px]">{p.name.startsWith("team_") ? "permit-only (tool composition)" : "auto-generated"}</Badge>}
              </div>
              {deleting === p.name ? (
                <span className="flex items-center gap-1">
                  <button onClick={() => handleDelete(p.name)} disabled={deletePending} className="px-2 py-1 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">{deletePending ? "..." : "Delete"}</button>
                  <button onClick={() => setDeleting(null)} className="px-2 py-1 text-xs border rounded-lg hover:bg-zinc-50">Cancel</button>
                </span>
              ) : (
                <button onClick={() => setDeleting(p.name)} className="text-xs text-zinc-400 hover:text-red-600">Delete</button>
              )}
            </div>
          ))}
          {!policy.policies.length && <p className="text-zinc-400 text-sm py-4 text-center">No policies yet. Click "Add Policy" to create one.</p>}
        </CardContent>
      </Card>
      <p className="mt-4 text-xs text-zinc-400 font-mono">Engine: {policy.engineArn}</p>
    </div>
  )
}
