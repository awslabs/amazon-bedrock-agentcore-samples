export interface Gateway { name: string; id: string; status: string; protocol: string; idp?: string }
export interface Tool { name: string; shortName: string; description: string }
export interface ToolGroup { target: string; tools: Tool[] }
export interface Client { name: string; clientId: string; allowed: boolean; createdAt?: string; lastModified?: string; scopes?: string[] }
export interface PolicyStatus { engineArn: string; mode: string; policies: { name: string; status: string }[] }
