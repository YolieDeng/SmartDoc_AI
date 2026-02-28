import { useState, useCallback, useRef } from 'react'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  tool?: string
  sources?: string[]
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState(false)
  const sessionId = useRef(Math.random().toString(36).slice(2) + Date.now().toString(36))
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(async (question: string) => {
    const userMsg: Message = { role: 'user', content: question }
    setMessages((prev) => [...prev, userMsg])
    setStreaming(true)

    // 占位 assistant 消息
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const resp = await fetch('/api/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          session_id: sessionId.current,
        }),
        signal: ctrl.signal,
      })

      if (!resp.ok || !resp.body) throw new Error('请求失败')

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // 解析 SSE 行
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()
          if (!raw || raw === '[DONE]') continue

          try {
            const evt = JSON.parse(raw)
            if (evt.type === 'token') {
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + evt.content,
                }
                return updated
              })
            } else if (evt.type === 'tool') {
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  tool: evt.name,
                }
                return updated
              })
            } else if (evt.type === 'sources') {
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  sources: evt.content,
                }
                return updated
              })
            } else if (evt.type === 'error') {
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: evt.content,
                }
                return updated
              })
            }
          } catch {
            // 忽略非 JSON 行
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: '请求出错，请重试。',
          }
          return updated
        })
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const clear = useCallback(() => {
    setMessages([])
    sessionId.current = Math.random().toString(36).slice(2) + Date.now().toString(36)
  }, [])

  return { messages, streaming, send, stop, clear }
}
