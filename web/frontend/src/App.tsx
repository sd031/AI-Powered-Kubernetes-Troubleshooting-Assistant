import { useCallback, useEffect, useRef, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatView } from './components/ChatView'
import { ScanView } from './components/ScanView'
import { RunbooksView } from './components/RunbooksView'
import { SettingsView } from './components/SettingsView'
import { useWebSocket } from './hooks/useWebSocket'
import { AgentEvent, ProviderInfo, Tab } from './types'

// Stable session ID per browser tab
const SESSION_ID = crypto.randomUUID()

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null)

  // Event fan-out: multiple views subscribe to the same WebSocket stream
  const listenersRef = useRef<Set<(ev: AgentEvent) => void>>(new Set())

  const handleEvent = useCallback((ev: AgentEvent) => {
    if (ev.type === 'provider_info') {
      setProviderInfo({
        provider: ev.provider,
        model: ev.model,
        context: ev.context,
        k8s_version: ev.k8s_version,
      })
      return
    }
    listenersRef.current.forEach(fn => fn(ev))
  }, [])

  const { status, send } = useWebSocket(SESSION_ID, handleEvent)

  // Views register/unregister themselves as listeners
  const onEvent = useCallback(
    (handler: (ev: AgentEvent) => void) => {
      listenersRef.current.add(handler)
      return () => { listenersRef.current.delete(handler) }
    },
    [],
  )

  // Reload provider info after settings save
  const handleSettingsSave = useCallback(() => {
    // A new session will be created on next WS connection
    window.location.reload()
  }, [])

  const isConnected = status === 'connected'

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">
      <Sidebar
        active={tab}
        onTab={setTab}
        status={status}
        providerInfo={providerInfo}
      />

      <main className="flex-1 min-w-0 overflow-hidden">
        {tab === 'chat' && (
          <ChatView
            providerInfo={providerInfo}
            onEvent={onEvent}
            send={send}
            isConnected={isConnected}
          />
        )}
        {tab === 'scan' && (
          <ScanView
            providerInfo={providerInfo}
            onEvent={onEvent}
            send={send}
            isConnected={isConnected}
          />
        )}
        {tab === 'runbooks' && <RunbooksView />}
        {tab === 'settings' && <SettingsView onSave={handleSettingsSave} />}
      </main>
    </div>
  )
}
