/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AGENT_RUNTIME_ARN: string
  readonly VITE_AGENT_ENDPOINT_NAME: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
