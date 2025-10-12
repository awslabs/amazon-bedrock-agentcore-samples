import { Sidebar } from './Sidebar'
import { ChatContainer } from './ChatContainer'

export function ChatPage() {
  return (
    <div className="min-h-screen bg-[#181c24] flex flex-col">
      {/* Header */}
      <header className="bg-[#1a1e27] border-b border-gray-700 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-200">
          Customer Support Assistant
        </h1>
        <div className="h-px bg-gradient-to-r from-[#298dff] to-transparent mt-2" />
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <ChatContainer />
      </div>
    </div>
  )
}
