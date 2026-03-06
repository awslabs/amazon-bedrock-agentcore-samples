import { signIn } from "@/lib/auth"

export default function LoginPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-zinc-50">
      <div className="text-center space-y-6">
        <h1 className="text-3xl font-bold">🚀 Agent & Gateway Registry</h1>
        <p className="text-zinc-500">Sign in to manage your agents, gateways, and policies</p>
        <form action={async () => { "use server"; await signIn("cognito") }}>
          <button type="submit" className="px-6 py-3 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800">
            Sign in with Cognito
          </button>
        </form>
      </div>
    </div>
  )
}
