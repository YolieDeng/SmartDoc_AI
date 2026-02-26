import FileUpload from './components/FileUpload'
import MessageList from './components/MessageList'
import ChatInput from './components/ChatInput'
import { useChat } from './hooks/useChat'

export default function App() {
  const { messages, streaming, send, stop, clear } = useChat()

  return (
    <div className="flex h-screen flex-col bg-white">
      {/* 顶栏 */}
      <header className="flex items-center justify-between border-b
                          border-gray-200 px-6 py-3">
        <h1 className="text-lg font-semibold text-gray-800">
          SmartDoc AI
        </h1>
        <div className="flex items-center gap-3">
          <FileUpload />
          <button
            onClick={clear}
            className="rounded-lg border border-gray-300 px-3 py-2
                       text-sm text-gray-600 hover:bg-gray-50
                       transition-colors"
          >
            新对话
          </button>
        </div>
      </header>

      {/* 消息区 */}
      <MessageList messages={messages} />

      {/* 输入区 */}
      <ChatInput
        onSend={send}
        onStop={stop}
        streaming={streaming}
      />
    </div>
  )
}
