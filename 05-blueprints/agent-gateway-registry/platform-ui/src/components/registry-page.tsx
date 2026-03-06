"use client"

import { useState } from "react"
import { Search, Plus, Package, RefreshCw, ChevronDown, ChevronRight, X, Globe, User, Tag, Bot, Wrench, Zap, Pencil, Trash2, Check } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { trpc } from "@/lib/trpc"

const PROTOCOLS = [
  { value: "mcp", label: "MCP Server", icon: Wrench, desc: "Tool server exposing tools via MCP protocol" },
  { value: "a2a", label: "A2A Agent", icon: Bot, desc: "Agent supporting A2A protocol (agent card + skills)" },
  { value: "a2a+mcp", label: "Agent-as-Tool", icon: Zap, desc: "Agent without A2A support — exposed as MCP tools (e.g. n8n, LangGraph, custom REST)" },
] as const

const protocolBadge = (p: string) => {
  if (p === "a2a") return <Badge className="bg-purple-100 text-purple-700">A2A</Badge>
  if (p === "a2a+mcp") return <Badge className="bg-amber-100 text-amber-700">A2A+MCP</Badge>
  return <Badge className="bg-blue-100 text-blue-700">MCP</Badge>
}

type FormState = { name: string; description: string; owner: string; repoUrl: string; runtimeArn: string; version: string; tags: string; gatewayName: string; targetName: string; protocol: string; endpointUrl: string }
const emptyForm: FormState = { name: "", description: "", owner: "", repoUrl: "", runtimeArn: "", version: "1.0.0", tags: "", gatewayName: "", targetName: "", protocol: "mcp", endpointUrl: "" }

type EditState = { description: string; owner: string; repoUrl: string; version: string; tags: string }

export function RegistryPage() {
  const [search, setSearch] = useState("")
  const [showForm, setShowForm] = useState(false)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<EditState>({ description: "", owner: "", repoUrl: "", version: "", tags: "" })
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [authToken, setAuthToken] = useState<Record<string, string>>({})
  const [showAuth, setShowAuth] = useState<string | null>(null)

  const utils = trpc.useUtils()
  const { data: servers = [], isLoading } = trpc.registry.list.useQuery(search ? { search } : undefined)
  const createMut = trpc.registry.create.useMutation({ onSuccess: () => { utils.registry.list.invalidate(); setShowForm(false); setForm(emptyForm) } })
  const updateMut = trpc.registry.update.useMutation({ onSuccess: () => { utils.registry.list.invalidate(); setEditingId(null) } })
  const deleteMut = trpc.registry.delete.useMutation({ onSuccess: () => { utils.registry.list.invalidate(); setDeletingId(null) } })
  const syncMut = trpc.registry.sync.useMutation({ onSuccess: () => utils.registry.list.invalidate() })
  const syncEndpointMut = trpc.registry.syncFromEndpoint.useMutation({ onSuccess: () => utils.registry.list.invalidate() })
  const fetchCardMut = trpc.registry.fetchCard.useMutation({ onSuccess: () => utils.registry.list.invalidate() })

  const handleCreate = () => {
    const { tags, ...rest } = form
    createMut.mutate({ ...rest, tags: tags ? tags.split(",").map(t => t.trim()) : undefined })
  }

  const startEdit = (s: typeof servers[number]) => {
    setEditingId(s.id)
    setEditForm({ description: s.description || "", owner: s.owner || "", repoUrl: s.repoUrl || "", version: s.version, tags: s.tags.join(", ") })
    setExpanded(p => ({ ...p, [s.id]: true }))
  }

  const saveEdit = () => {
    if (!editingId) return
    const { tags, ...rest } = editForm
    updateMut.mutate({ id: editingId, data: { ...rest, tags: tags ? tags.split(",").map(t => t.trim()) : [] } })
  }

  const parseSkills = (s: string): Array<{ name?: string; id?: string; description?: string }> => {
    try { return JSON.parse(s) } catch { return [] }
  }

  const showMcp = form.protocol === "mcp" || form.protocol === "a2a+mcp"
  const showA2a = form.protocol === "a2a" || form.protocol === "a2a+mcp"

  const inp = "px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Agent & Tool Registry</h2>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800">
          <Plus size={16} /> Register
        </button>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search agents, tools, or tags..." className="w-full pl-10 pr-4 py-2.5 rounded-lg border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
      </div>

      {/* Create form */}
      {showForm && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Register Agent or Server</CardTitle>
              <button onClick={() => setShowForm(false)}><X size={18} className="text-zinc-400" /></button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-4">
              {PROTOCOLS.map(p => (
                <button key={p.value} onClick={() => setForm(f => ({ ...f, protocol: p.value }))} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${form.protocol === p.value ? "border-zinc-900 bg-zinc-900 text-white" : "hover:bg-zinc-50"}`}>
                  <p.icon size={14} />
                  {p.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-zinc-400 mb-4">{PROTOCOLS.find(p => p.value === form.protocol)?.desc}</p>
            <div className="grid grid-cols-2 gap-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Name" className={inp} />
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" className={inp} />
              <input value={form.owner} onChange={e => setForm(f => ({ ...f, owner: e.target.value }))} placeholder="Owner" className={inp} />
              <input value={form.version} onChange={e => setForm(f => ({ ...f, version: e.target.value }))} placeholder="Version" className={inp} />
              {showA2a && <input value={form.endpointUrl} onChange={e => setForm(f => ({ ...f, endpointUrl: e.target.value }))} placeholder="Endpoint URL or ARN" className={inp} />}
              {showA2a && <input value={form.runtimeArn} onChange={e => setForm(f => ({ ...f, runtimeArn: e.target.value }))} placeholder="Runtime ARN (optional)" className={inp} />}
              {showMcp && <input value={form.gatewayName} onChange={e => setForm(f => ({ ...f, gatewayName: e.target.value }))} placeholder="Gateway Name" className={inp} />}
              {showMcp && <input value={form.targetName} onChange={e => setForm(f => ({ ...f, targetName: e.target.value }))} placeholder="Target Name" className={inp} />}
              <input value={form.repoUrl} onChange={e => setForm(f => ({ ...f, repoUrl: e.target.value }))} placeholder="Repo URL" className={inp} />
              <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="Tags (comma-separated)" className={inp} />
            </div>
            <button onClick={handleCreate} disabled={!form.name || createMut.isPending} className="mt-4 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800 disabled:opacity-50">
              {createMut.isPending ? "Registering..." : "Register"}
            </button>
          </CardContent>
        </Card>
      )}

      {/* List */}
      {isLoading ? <p className="text-zinc-400">Loading registry...</p> : (
        <div className="space-y-3">
          {servers.map(server => {
            const isOpen = expanded[server.id]
            const isEditing = editingId === server.id
            const isDeleting = deletingId === server.id
            const isA2a = (server.protocol || "mcp").includes("a2a")
            const isMcp = (server.protocol || "mcp").includes("mcp")
            const skills = parseSkills(server.skills || "[]")
            return (
              <Card key={server.id} className={isDeleting ? "border-red-200 bg-red-50/50" : ""}>
                <div className="p-4">
                  {/* Header row */}
                  <div className="flex items-start justify-between">
                    <button onClick={() => setExpanded(p => ({ ...p, [server.id]: !isOpen }))} className="flex items-center gap-2 text-left">
                      {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      {isA2a ? <Bot size={18} className="text-purple-500" /> : <Package size={18} className="text-zinc-500" />}
                      <div>
                        <span className="font-semibold">{server.name}</span>
                        {protocolBadge(server.protocol || "mcp")}
                        <Badge variant="secondary" className="ml-1">v{server.version}</Badge>
                        {server.tools.length > 0 && <Badge variant="outline" className="ml-1">{server.tools.length} tools</Badge>}
                        {skills.length > 0 && <Badge variant="outline" className="ml-1">{skills.length} skills</Badge>}
                      </div>
                    </button>
                    <div className="flex gap-1">
                      {server.protocol === "a2a" && (server.endpointUrl || server.runtimeArn) && (
                        <button onClick={() => fetchCardMut.mutate({ id: server.id })} disabled={fetchCardMut.isPending} className="flex items-center gap-1 px-3 py-1.5 text-xs border rounded-lg hover:bg-zinc-50 disabled:opacity-50">
                          <RefreshCw size={14} className={fetchCardMut.isPending ? "animate-spin" : ""} /> Fetch Card
                        </button>
                      )}
                      {isMcp && server.gatewayName && (
                        <button onClick={() => syncMut.mutate({ serverId: server.id, gatewayName: server.gatewayName! })} disabled={syncMut.isPending} className="flex items-center gap-1 px-3 py-1.5 text-xs border rounded-lg hover:bg-zinc-50 disabled:opacity-50">
                          <RefreshCw size={14} className={syncMut.isPending ? "animate-spin" : ""} /> Sync Tools
                        </button>
                      )}
                      {isMcp && !server.gatewayName && server.endpointUrl && (
                        showAuth === server.id ? (
                          <div className="flex items-center gap-1">
                            <input value={authToken[server.id] || ""} onChange={e => setAuthToken(p => ({ ...p, [server.id]: e.target.value }))} placeholder="Bearer token (optional)" className="px-2 py-1 text-xs border rounded-lg w-48 focus:outline-none" />
                            <button onClick={() => { syncEndpointMut.mutate({ id: server.id, authHeader: authToken[server.id] || undefined }); setShowAuth(null) }} disabled={syncEndpointMut.isPending} className="px-2 py-1 text-xs bg-zinc-900 text-white rounded-lg hover:bg-zinc-800 disabled:opacity-50">
                              {syncEndpointMut.isPending ? "..." : "Sync"}
                            </button>
                            <button onClick={() => setShowAuth(null)} className="px-2 py-1 text-xs border rounded-lg hover:bg-zinc-50">✕</button>
                          </div>
                        ) : (
                          <button onClick={() => setShowAuth(server.id)} disabled={syncEndpointMut.isPending} className="flex items-center gap-1 px-3 py-1.5 text-xs border rounded-lg hover:bg-zinc-50 disabled:opacity-50">
                            <RefreshCw size={14} className={syncEndpointMut.isPending ? "animate-spin" : ""} /> Sync Tools
                          </button>
                        )
                      )}
                      {!isEditing && (
                        <button onClick={() => startEdit(server)} className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100" title="Edit">
                          <Pencil size={14} />
                        </button>
                      )}
                      {!isDeleting ? (
                        <button onClick={() => setDeletingId(server.id)} className="p-1.5 text-zinc-400 hover:text-red-600 rounded-lg hover:bg-red-50" title="Delete">
                          <Trash2 size={14} />
                        </button>
                      ) : (
                        <div className="flex items-center gap-1 ml-1">
                          <button onClick={() => deleteMut.mutate({ id: server.id })} disabled={deleteMut.isPending} className="px-2 py-1 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">
                            {deleteMut.isPending ? "..." : "Delete"}
                          </button>
                          <button onClick={() => setDeletingId(null)} className="px-2 py-1 text-xs border rounded-lg hover:bg-zinc-50">Cancel</button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Description + meta */}
                  {!isEditing && server.description && <p className="text-sm text-zinc-500 mt-1 ml-9">{server.description}</p>}
                  {!isEditing && server.protocol === "a2a+mcp" && <p className="text-xs text-amber-600 mt-1 ml-9">⚡ Agent without A2A support — exposed as MCP tools</p>}
                  {!isEditing && (
                    <div className="flex items-center gap-4 mt-2 ml-9 text-xs text-zinc-400">
                      {server.owner && <span className="flex items-center gap-1"><User size={12} />{server.owner}</span>}
                      {server.endpointUrl && <span className="flex items-center gap-1 truncate max-w-xs"><Globe size={12} />{server.endpointUrl}</span>}
                      {!server.endpointUrl && server.repoUrl && <span className="flex items-center gap-1"><Globe size={12} />{server.repoUrl}</span>}
                      {server.tags.length > 0 && <span className="flex items-center gap-1"><Tag size={12} />{server.tags.join(", ")}</span>}
                    </div>
                  )}

                  {/* Inline edit form */}
                  {isEditing && (
                    <div className="mt-3 ml-9 p-3 rounded-lg border bg-zinc-50 space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <input value={editForm.description} onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" className={inp + " bg-white"} />
                        <input value={editForm.owner} onChange={e => setEditForm(f => ({ ...f, owner: e.target.value }))} placeholder="Owner" className={inp + " bg-white"} />
                        <input value={editForm.version} onChange={e => setEditForm(f => ({ ...f, version: e.target.value }))} placeholder="Version" className={inp + " bg-white"} />
                        <input value={editForm.tags} onChange={e => setEditForm(f => ({ ...f, tags: e.target.value }))} placeholder="Tags (comma-separated)" className={inp + " bg-white"} />
                        <input value={editForm.repoUrl} onChange={e => setEditForm(f => ({ ...f, repoUrl: e.target.value }))} placeholder="Repo URL" className={inp + " bg-white col-span-2"} />
                      </div>
                      <div className="flex gap-2">
                        <button onClick={saveEdit} disabled={updateMut.isPending} className="flex items-center gap-1 px-3 py-1.5 bg-zinc-900 text-white rounded-lg text-xs hover:bg-zinc-800 disabled:opacity-50">
                          <Check size={12} /> {updateMut.isPending ? "Saving..." : "Save"}
                        </button>
                        <button onClick={() => setEditingId(null)} className="px-3 py-1.5 border rounded-lg text-xs hover:bg-white">Cancel</button>
                      </div>
                    </div>
                  )}

                  {/* Expanded: skills + tools */}
                  {isOpen && !isEditing && (
                    <div className="mt-3 ml-9 space-y-1">
                      {skills.length > 0 && (
                        <>
                          <p className="text-xs font-medium text-zinc-500 mb-1">Skills</p>
                          {skills.map((s, i) => (
                            <div key={i} className="p-2 rounded border bg-purple-50 text-sm">
                              <span className="font-medium">{s.name || s.id}</span>
                              {s.description && <span className="text-zinc-500 ml-2">{s.description}</span>}
                            </div>
                          ))}
                        </>
                      )}
                      {server.tools.length > 0 && (
                        <>
                          {skills.length > 0 && <p className="text-xs font-medium text-zinc-500 mb-1 mt-3">Tools</p>}
                          {server.tools.map(t => (
                            <div key={t.id} className="p-2 rounded border bg-zinc-50 text-sm">
                              <span className="font-medium">{t.shortName}</span>
                              {t.description && <span className="text-zinc-500 ml-2">{t.description}</span>}
                            </div>
                          ))}
                        </>
                      )}
                      {!skills.length && !server.tools.length && (
                        <p className="text-xs text-zinc-400">{isA2a ? "Click 'Fetch Card' to load skills" : "Click 'Sync Tools' to load tools"}</p>
                      )}
                    </div>
                  )}
                </div>
              </Card>
            )
          })}
          {!servers.length && <p className="text-center text-zinc-400 py-8">No agents or servers registered yet.</p>}
        </div>
      )}
    </div>
  )
}
