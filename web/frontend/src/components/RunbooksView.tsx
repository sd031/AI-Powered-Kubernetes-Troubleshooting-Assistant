import { useCallback, useEffect, useState } from 'react'
import { BookOpen, Trash2, RefreshCw, ChevronLeft, Calendar, FileText } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { RunbookMeta } from '../types'

export function RunbooksView() {
  const [runbooks, setRunbooks] = useState<RunbookMeta[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [contentLoading, setContentLoading] = useState(false)

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/runbooks')
      const data = await res.json()
      setRunbooks(data.runbooks ?? [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  const openRunbook = async (filename: string) => {
    setSelected(filename)
    setContent('')
    setContentLoading(true)
    try {
      const res = await fetch(`/api/runbooks/${encodeURIComponent(filename)}`)
      const data = await res.json()
      setContent(data.content ?? '')
    } finally {
      setContentLoading(false)
    }
  }

  const deleteRunbook = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`Delete ${filename}?`)) return
    await fetch(`/api/runbooks/${encodeURIComponent(filename)}`, { method: 'DELETE' })
    if (selected === filename) { setSelected(null); setContent('') }
    fetchList()
  }

  // ── Detail view ────────────────────────────────────────────────────────────
  if (selected) return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800 shrink-0">
        <button
          onClick={() => { setSelected(null); setContent('') }}
          className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
        >
          <ChevronLeft size={16} /> Back
        </button>
        <span className="text-gray-600 text-sm">·</span>
        <span className="text-sm text-gray-300 truncate">{selected}</span>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {contentLoading ? (
          <div className="flex items-center gap-2 text-gray-500 text-sm">
            <RefreshCw size={14} className="animate-spin" /> Loading…
          </div>
        ) : (
          <div className="prose-k8s max-w-3xl mx-auto text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )

  // ── List view ──────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 shrink-0">
        <h2 className="font-semibold text-white flex items-center gap-2">
          <BookOpen size={16} /> Runbooks
          {runbooks.length > 0 && (
            <span className="text-xs bg-gray-700 text-gray-300 rounded-full px-2 py-0.5">
              {runbooks.length}
            </span>
          )}
        </h2>
        <button
          onClick={fetchList}
          className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {runbooks.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <FileText size={40} className="text-gray-700" />
            <p className="text-gray-500 text-sm">No runbooks yet.</p>
            <p className="text-gray-600 text-xs">
              Run a scan or fix a problem to auto-generate a runbook.
            </p>
          </div>
        )}
        <div className="space-y-2">
          {runbooks.map(rb => (
            <button
              key={rb.filename}
              onClick={() => openRunbook(rb.filename)}
              className="w-full text-left p-3.5 rounded-xl bg-gray-800 border border-gray-700
                         hover:border-blue-500 hover:bg-gray-750 transition-all group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-100 truncate group-hover:text-white">
                    {rb.title}
                  </p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="flex items-center gap-1 text-xs text-gray-500">
                      <Calendar size={10} /> {rb.date}
                    </span>
                    <span className="text-xs text-gray-600">
                      {(rb.size / 1024).toFixed(1)} KB
                    </span>
                  </div>
                </div>
                <button
                  onClick={e => deleteRunbook(rb.filename, e)}
                  className="shrink-0 p-1.5 rounded-lg text-gray-600 hover:text-red-400
                             hover:bg-red-900/30 transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
