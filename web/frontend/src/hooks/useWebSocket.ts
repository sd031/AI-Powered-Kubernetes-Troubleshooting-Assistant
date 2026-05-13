import { useCallback, useEffect, useRef, useState } from 'react'
import { AgentEvent } from '../types'

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketReturn {
  status: WsStatus
  send: (msg: object) => void
  lastEvent: AgentEvent | null
}

export function useWebSocket(
  sessionId: string,
  onEvent: (event: AgentEvent) => void,
): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<WsStatus>('connecting')
  const [lastEvent, setLastEvent] = useState<AgentEvent | null>(null)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${proto}://${host}/ws/${sessionId}`

    const ws = new WebSocket(url)
    wsRef.current = ws
    setStatus('connecting')

    ws.onopen = () => setStatus('connected')

    ws.onmessage = (ev) => {
      try {
        const event: AgentEvent = JSON.parse(ev.data)
        setLastEvent(event)
        onEventRef.current(event)
      } catch { /* ignore parse errors */ }
    }

    ws.onerror = () => setStatus('error')

    ws.onclose = () => {
      setStatus('disconnected')
      // Reconnect after 2 s
      setTimeout(() => {
        if (wsRef.current === ws) {
          setStatus('connecting')
        }
      }, 2000)
    }

    return () => {
      wsRef.current = null
      ws.close()
    }
  }, [sessionId])

  const send = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return { status, send, lastEvent }
}
