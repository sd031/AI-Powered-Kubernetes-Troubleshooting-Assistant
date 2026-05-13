import { useEffect, useRef, useState, useCallback } from 'react'
import { Send, Trash2, Scan } from 'lucide-react'
import { ChatMessage, AgentEvent, ProviderInfo } from '../types'
import { MessageBubble } from './MessageBubble'
import { ConfirmDialog } from './ConfirmDialog'

let msgCounter = 0
const nextId = () => `msg-${++msgCounter}`

interface Props {
  providerInfo: ProviderInfo | null
  onEvent: (handler: (ev: AgentEvent) => void) => () => void
  send: (msg: object) => void
  isConnected: boolean
}

export function ChatView({ providerInfo, onEvent, send, isConnected }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: nextId(),
      role: 'system',
      content: 'Session started — describe an issue or type "scan" for a full cluster scan.',
      toolCalls: [],
      isStreaming: false,
      isError: false,
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState<{ id: string; action: string } | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const currentAssistantId = useRef<string | null>(null)

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const updateCurrentAssistant = useCallback((updater: (prev: ChatMessage) => ChatMessage) => {
    setMessages(msgs =>
      msgs.map(m => m.id === currentAssistantId.current ? updater(m) : m)
    )
  }, [])

  // Handle incoming agent events
  useEffect(() => {
    return onEvent((ev: AgentEvent) => {
      switch (ev.type) {
        case 'text': {
          if (!currentAssistantId.current) {
            const id = nextId()
            currentAssistantId.current = id
            setMessages(prev => [...prev, {
              id, role: 'assistant', content: ev.content,
              toolCalls: [], isStreaming: true, isError: false,
            }])
          } else {
            updateCurrentAssistant(m => ({ ...m, content: ev.content }))
          }
          break
        }
        case 'tool_call': {
          if (!currentAssistantId.current) {
            const id = nextId()
            currentAssistantId.current = id
            setMessages(prev => [...prev, {
              id, role: 'assistant', content: '',
              toolCalls: [{ id: ev.id, name: ev.name, args: ev.args, done: false }],
              isStreaming: true, isError: false,
            }])
          } else {
            updateCurrentAssistant(m => ({
              ...m,
              toolCalls: [...m.toolCalls, { id: ev.id, name: ev.name, args: ev.args, done: false }],
            }))
          }
          break
        }
        case 'tool_result': {
          updateCurrentAssistant(m => ({
            ...m,
            toolCalls: m.toolCalls.map(tc =>
              tc.id === ev.id
                ? { ...tc, preview: ev.preview, lineCount: ev.line_count, done: true }
                : tc
            ),
          }))
          break
        }
        case 'done': {
          updateCurrentAssistant(m => ({ ...m, isStreaming: false }))
          currentAssistantId.current = null
          setBusy(false)
          break
        }
        case 'error': {
          const id = currentAssistantId.current ?? nextId()
          currentAssistantId.current = null
          setMessages(prev => {
            const exists = prev.some(m => m.id === id)
            if (exists) {
              return prev.map(m => m.id === id
                ? { ...m, content: ev.message, isError: true, isStreaming: false }
                : m)
            }
            return [...prev, {
              id, role: 'assistant', content: ev.message,
              toolCalls: [], isStreaming: false, isError: true,
            }]
          })
          setBusy(false)
          break
        }
        case 'status': {
          setMessages(prev => [...prev, {
            id: nextId(), role: 'system', content: ev.message,
            toolCalls: [], isStreaming: false, isError: false,
          }])
          break
        }
        case 'runbook': {
          setMessages(prev => [...prev, {
            id: nextId(), role: 'system',
            content: `📄 Runbook saved: ${ev.filename}`,
            toolCalls: [], isStreaming: false, isError: false,
          }])
          break
        }
        case 'confirmation_required': {
          setPendingConfirm({ id: ev.id, action: ev.action })
          break
        }
        case 'reset_ack': {
          setMessages([{
            id: nextId(), role: 'system',
            content: 'Conversation cleared.',
            toolCalls: [], isStreaming: false, isError: false,
          }])
          currentAssistantId.current = null
          setBusy(false)
          break
        }
      }
    })
  }, [onEvent, updateCurrentAssistant])

  const handleSend = () => {
    const text = input.trim()
    if (!text || !isConnected || busy) return

    const isScan = text.toLowerCase() === 'scan'
    setMessages(prev => [...prev, {
      id: nextId(), role: 'user', content: text,
      toolCalls: [], isStreaming: false, isError: false,
    }])
    currentAssistantId.current = null
    setBusy(true)
    setInput('')

    if (isScan) {
      send({ type: 'scan' })
    } else {
      send({ type: 'message', content: text })
    }
  }

  const handleConfirm = (answer: boolean) => {
    if (!pendingConfirm) return
    send({ type: 'confirm', id: pendingConfirm.id, answer })
    setPendingConfirm(null)
  }

  const handleClear = () => {
    setBusy(false)
    send({ type: 'reset' })
  }

  const handleScan = () => {
    if (busy || !isConnected) return
    setMessages(prev => [...prev, {
      id: nextId(), role: 'user', content: 'Run a comprehensive cluster health scan',
      toolCalls: [], isStreaming: false, isError: false,
    }])
    currentAssistantId.current = null
    setBusy(true)
    send({ type: 'scan' })
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-white">Chat</h2>
          {providerInfo && (
            <span className="text-xs bg-gray-800 text-gray-400 rounded-full px-2 py-0.5">
              {providerInfo.provider} · {providerInfo.model}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            disabled={busy || !isConnected}
            title="Quick cluster scan"
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                       bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white
                       disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Scan size={13} /> Scan
          </button>
          <button
            onClick={handleClear}
            title="Clear conversation"
            className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-800 shrink-0">
        <div className="flex items-end gap-2 bg-gray-800 rounded-xl px-3 py-2 border border-gray-700
                        focus-within:border-blue-500 transition-colors">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder={
              !isConnected
                ? 'Connecting to backend…'
                : busy
                ? 'Agent is working…'
                : 'Describe a Kubernetes issue, or type "scan"… (Enter to send)'
            }
            disabled={!isConnected || busy}
            rows={1}
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500
                       resize-none outline-none max-h-32 min-h-[24px] leading-6
                       disabled:cursor-not-allowed"
            style={{ height: 'auto' }}
            onInput={e => {
              const t = e.target as HTMLTextAreaElement
              t.style.height = 'auto'
              t.style.height = `${Math.min(t.scrollHeight, 128)}px`
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || !isConnected || busy}
            className="shrink-0 w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center
                       hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            <Send size={14} className="text-white" />
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-1.5 text-center">
          Shift+Enter for new line · Destructive actions require confirmation
        </p>
      </div>

      {pendingConfirm && (
        <ConfirmDialog action={pendingConfirm.action} onAnswer={handleConfirm} />
      )}
    </div>
  )
}
