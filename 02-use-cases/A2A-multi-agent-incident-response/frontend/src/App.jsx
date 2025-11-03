import { ChatProvider } from './hooks/useChat'
import { ChatPage } from './components/ChatPage'

function App() {
  return (
    <ChatProvider>
      <ChatPage />
    </ChatProvider>
  )
}

export default App
