import { MessageSquare, Search, BookOpen, Settings, Wifi, WifiOff, Loader } from 'lucide-react'
import { Tab, ProviderInfo } from '../types'
import { WsStatus } from '../hooks/useWebSocket'

interface Props {
  active: Tab
  onTab: (t: Tab) => void
  status: WsStatus
  providerInfo: ProviderInfo | null
}

const TABS: { id: Tab; label: string; Icon: typeof MessageSquare }[] = [
  { id: 'chat',     label: 'Chat',     Icon: MessageSquare },
  { id: 'scan',     label: 'Scan',     Icon: Search },
  { id: 'runbooks', label: 'Runbooks', Icon: BookOpen },
  { id: 'settings', label: 'Settings', Icon: Settings },
]

export function Sidebar({ active, onTab, status, providerInfo }: Props) {
  const StatusIcon =
    status === 'connected'    ? Wifi :
    status === 'connecting'   ? Loader :
    WifiOff

  const statusColor =
    status === 'connected'    ? 'text-green-400' :
    status === 'connecting'   ? 'text-yellow-400' :
    'text-red-400'

  return (
    <aside className="w-14 md:w-52 flex flex-col bg-gray-900 border-r border-gray-800 shrink-0">
      {/* Logo */}
      <div className="px-3 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">⎈</span>
          <div className="hidden md:block min-w-0">
            <p className="text-xs font-bold text-white leading-tight">K8s AI</p>
            <p className="text-xs text-gray-500 leading-tight truncate">Troubleshooter</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-1 px-2">
        {TABS.map(({ id, label, Icon }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              onClick={() => onTab(id)}
              className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm
                transition-colors text-left
                ${isActive
                  ? 'bg-blue-600/20 text-blue-400 font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}`}
            >
              <Icon size={16} className="shrink-0" />
              <span className="hidden md:block">{label}</span>
            </button>
          )
        })}
      </nav>

      {/* Connection status + provider */}
      <div className="px-3 py-3 border-t border-gray-800 space-y-2">
        <div className={`flex items-center gap-1.5 text-xs ${statusColor}`}>
          <StatusIcon size={11} className={status === 'connecting' ? 'animate-spin' : ''} />
          <span className="hidden md:block capitalize">{status}</span>
        </div>
        {providerInfo && (
          <div className="hidden md:block text-xs text-gray-600 space-y-0.5 leading-tight">
            <p className="truncate text-gray-500">{providerInfo.provider}</p>
            <p className="truncate">{providerInfo.context}</p>
            <p className="truncate">{providerInfo.k8s_version}</p>
          </div>
        )}
      </div>
    </aside>
  )
}
