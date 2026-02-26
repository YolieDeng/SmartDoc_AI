import { useEffect, useRef } from 'react'
import type { Message } from '../hooks/useChat'

interface Props {
  messages: Message[]
}

export default function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center
                      text-gray-400">
        上传 PDF 后，开始提问吧
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-4">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex ${
            msg.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm
                        whitespace-pre-wrap ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-800'
            }`}
          >
            {msg.tool && (
              <div className="mb-1 text-xs text-gray-400">
                {msg.tool === 'web_search' ? '🌐 网络搜索' : '📄 文档检索'}
              </div>
            )}
            {msg.content || '...'}
            {msg.sources && msg.sources.length > 0 && (
              <details className="mt-2 text-xs text-gray-400">
                <summary className="cursor-pointer">参考来源 ({msg.sources.length})</summary>
                <ul className="mt-1 space-y-1 list-disc pl-4">
                  {msg.sources.map((s, j) => (
                    <li key={j}>{s.slice(0, 100)}...</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
