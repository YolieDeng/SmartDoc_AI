import { useState, useCallback } from 'react'

interface Props {
  onSend: (question: string) => void
  onStop: () => void
  streaming: boolean
}

export default function ChatInput({ onSend, onStop, streaming }: Props) {
  const [text, setText] = useState('')

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      const q = text.trim()
      if (!q || streaming) return
      onSend(q)
      setText('')
    },
    [text, streaming, onSend],
  )

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 border-t
                                             border-gray-200">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="输入你的问题..."
        className="flex-1 rounded-lg border border-gray-300 px-4 py-2
                   text-sm focus:border-blue-500 focus:outline-none"
        disabled={streaming}
        aria-label="输入问题"
      />
      {streaming ? (
        <button
          type="button"
          onClick={onStop}
          className="rounded-lg bg-red-500 px-4 py-2 text-sm
                     text-white hover:bg-red-600 transition-colors"
        >
          停止
        </button>
      ) : (
        <button
          type="submit"
          disabled={!text.trim()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm
                     text-white hover:bg-blue-700 transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          发送
        </button>
      )}
    </form>
  )
}
