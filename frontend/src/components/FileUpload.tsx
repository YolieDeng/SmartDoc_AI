import { useState, useCallback } from 'react'

export default function FileUpload() {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return

      setUploading(true)
      setResult(null)

      const form = new FormData()
      form.append('file', file)

      try {
        const resp = await fetch('/api/upload', {
          method: 'POST',
          body: form,
        })
        const data = await resp.json()
        if (resp.ok) {
          setResult(`上传成功，共 ${data.chunks_count} 个文本块`)
        } else {
          setResult(data.detail || '上传失败')
        }
      } catch {
        setResult('网络错误')
      } finally {
        setUploading(false)
        e.target.value = ''
      }
    },
    [],
  )

  return (
    <div className="flex items-center gap-3">
      <label
        className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2
                   text-sm text-white hover:bg-blue-700
                   transition-colors"
        aria-label="上传 PDF 文件"
      >
        {uploading ? '上传中...' : '上传 PDF'}
        <input
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleUpload}
          disabled={uploading}
        />
      </label>
      {result && (
        <span className="text-sm text-gray-500">{result}</span>
      )}
    </div>
  )
}
