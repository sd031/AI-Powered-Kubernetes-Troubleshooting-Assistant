import { useEffect, useRef, useState } from 'react'
import { Play, CheckCircle, Loader, AlertCircle, BookOpen } from 'lucide-react'
import { AgentEvent, ProviderInfo } from '../types'
import { ConfirmDialog } from './ConfirmDialog'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface LogEntry {
  kind: 'tool' | 'result' | 'text' | 'status' | 'error' | 'runbook'
  name?: string
  content: string
}

interface Props {
  providerInfo: ProviderInfo | null
  onEvent: (handler: (ev: AgentEvent) => void) => () => void
  send: (msg: object) => void
  isConnected: boolean
}

export function ScanView({ providerInfo, onEvent, send, isConnected }: Props) {
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  const [log, setLog] = useState<LogEntry[]>([])
  const [summary, setSummary] = useState('')
  const [runbookFile, setRunbookFile] = useState('')
  const [pendingConfirm, setPendingConfirm] = useState<{ id: string; action: string } | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [log])

  useEffect(() => {
    return onEvent((ev: AgentEvent) => {
      switch (ev.type) {
        case 'tool_call':
          setLog(l => [...l, { kind: 'tool', name: ev.name, content: JSON.stringify(ev.args) }])
          break
        case 'tool_result':
          setLog(l => [...l, { kind: 'result', name: ev.name, content: ev.preview }])
          break
        case 'text':
          setSummary(ev.content)
          break
        case 'status':
          setLog(l => [...l, { kind: 'status', content: ev.message }])
          break
        case 'error':
          setLog(l => [...l, { kind: 'error', content: ev.message }])
          setRunning(false)
          break
        case 'done':
          setRunning(false)
          setDone(true)
          break
        case 'runbook':
          setRunbookFile(ev.filename)
          setLog(l => [...l, { kind: 'runbook', content: ev.filename }])
          break
        case 'confirmation_required':
          setPendingConfirm({ id: ev.id, action: ev.action })
          break
      }
    })
  }, [onEvent])

  const startScan = () => {
    setLog([])
    setSummary('')
    setRunbookFile('')
    setDone(false)
    setRunning(true)
    send({ type: 'scan' })
  }

  const handleConfirm = (answer: boolean) => {
    if (!pendingConfirm) return
    send({ type: 'confirm', id: pendingConfirm.id, answer })
    setPendingConfirm(null)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-white">Cluster Scan</h2>
          {providerInfo && (
            <span className="text-xs bg-gray-800 text-gray-400 rounded-full px-2 py-0.5">
              {providerInfo.context}
            </span>
          )}
        </div>
        <button
          onClick={startScan}
          disabled={running || !isConnected}
          className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-blue-600 text-white text-sm
                     hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors font-medium"
        >
          {running
            ? <><Loader size={14} className="animate-spin" /> Scanning…</>
            : <><Play size={14} /> Run Scan</>}
        </button>
      </div>

      <div className="flex-1 overflow-hidden flex flex-col gap-0 p-4">
        {/* Initial state */}
        {!running && !done && log.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center">
            <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center text-3xl">
              🏥
            </div>
            <div>
              <h3 className="text-white font-semibold text-lg mb-1">Comprehensive Cluster Scan</h3>
              <p className="text-gray-400 text-sm max-w-sm">
                The AI will inspect all nodes, pods, events, and resources across every namespace,
                diagnose issues, and generate a runbook.
              </p>
            </div>
            <button
              onClick={startScan}
              disabled={!isConnected}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 text-white
                         hover:bg-blue-500 disabled:opacity-40 transition-colors font-medium"
            >
              <Play size={16} /> Start Scan
            </button>
          </div>
        )}

        {/* Activity log */}
        {log.length > 0 && (
          <div className="flex flex-col gap-3 overflow-hidden flex-1">
            <div ref={logRef} className="overflow-y-auto flex-1 space-y-1.5 pr-1">
              {log.map((entry, i) => (
                <LogLine key={i} entry={entry} />
              ))}
              {running && (
                <div className="flex items-center gap-2 text-xs text-yellow-400 py-1">
                  <Loader size={12} className="animate-spin" />
                  <span>Agent is working…</span>
                </div>
              )}
            </div>

            {/* Summary */}
            {summary && (
              <div className="border-t border-gray-700 pt-3 overflow-y-auto max-h-64">
                <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-1.5">
                  {done
                    ? <CheckCircle size={14} className="text-green-400" />
                    : <Loader size={14} className="animate-spin text-yellow-400" />}
                  AI Analysis
                </h3>
                <div className="prose-k8s text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
                </div>
              </div>
            )}

            {/* Runbook badge */}
            {runbookFile && (
              <div className="flex items-center gap-2 p-2.5 bg-green-900/30 border border-green-700
                              rounded-lg text-sm text-green-300">
                <BookOpen size={14} />
                <span>Runbook saved: <code className="font-mono text-xs">{runbookFile}</code></span>
              </div>
            )}
          </div>
        )}
      </div>

      {pendingConfirm && (
        <ConfirmDialog action={pendingConfirm.action} onAnswer={handleConfirm} />
      )}
    </div>
  )
}

function LogLine({ entry }: { entry: LogEntry }) {
  if (entry.kind === 'tool') return (
    <div className="flex items-center gap-2 text-xs font-mono py-0.5">
      <span className="text-cyan-500 shrink-0">⚙</span>
      <span className="text-cyan-400">{entry.name}</span>
      <span className="text-gray-600 truncate">{entry.content}</span>
    </div>
  )
  if (entry.kind === 'result') return (
    <div className="flex items-start gap-2 text-xs font-mono py-0.5">
      <span className="text-green-500 shrink-0 mt-0.5">↳</span>
      <span className="text-green-400 shrink-0">{entry.name}</span>
      <span className="text-gray-500 truncate">{entry.content.split('\n')[0]}</span>
    </div>
  )
  if (entry.kind === 'error') return (
    <div className="flex items-center gap-2 text-xs text-red-400 py-0.5">
      <AlertCircle size={11} className="shrink-0" />
      <span>{entry.content}</span>
    </div>
  )
  if (entry.kind === 'runbook') return (
    <div className="flex items-center gap-2 text-xs text-green-400 py-0.5">
      <BookOpen size={11} className="shrink-0" />
      <span>Runbook: {entry.content}</span>
    </div>
  )
  return (
    <div className="text-xs text-gray-500 py-0.5">{entry.content}</div>
  )
}
