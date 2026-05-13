import { useState } from 'react'
import { ChevronDown, ChevronRight, Terminal, CheckCircle, Loader } from 'lucide-react'
import { ToolCallRecord } from '../types'

const TOOL_ICONS: Record<string, string> = {
  check_cluster_health: '🏥',
  get_pods: '🫛',
  get_pod_logs: '📋',
  get_events: '⚡',
  describe_pod: '🔍',
  get_nodes: '🖥',
  describe_node: '🖥',
  get_deployments: '🚀',
  get_services: '🌐',
  get_pvcs: '💾',
  get_persistent_volumes: '💾',
  get_configmaps: '⚙️',
  get_resource_quotas: '📊',
  restart_deployment: '🔄',
  rollback_deployment: '⏪',
  scale_deployment: '📈',
  delete_pod: '🗑',
  apply_manifest: '✅',
  patch_resource: '🩹',
  run_kubectl: '⌨️',
  list_namespaces: '📁',
  get_hpa: '📈',
}

export function ToolCallCard({ tc }: { tc: ToolCallRecord }) {
  const [open, setOpen] = useState(false)
  const icon = TOOL_ICONS[tc.name] ?? '🔧'
  const hasResult = tc.preview !== undefined

  return (
    <div className="my-1 rounded-lg border border-gray-700 bg-gray-900 text-sm overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-gray-800 transition-colors"
      >
        <span className="text-base">{icon}</span>
        <code className="flex-1 text-cyan-400 font-mono text-xs">{tc.name}</code>
        {!hasResult && !tc.done && (
          <Loader size={13} className="text-yellow-400 animate-spin shrink-0" />
        )}
        {hasResult && (
          <CheckCircle size={13} className="text-green-400 shrink-0" />
        )}
        {open ? (
          <ChevronDown size={14} className="text-gray-500 shrink-0" />
        ) : (
          <ChevronRight size={14} className="text-gray-500 shrink-0" />
        )}
      </button>

      {open && (
        <div className="border-t border-gray-700 px-3 py-2 space-y-2">
          {/* Args */}
          {Object.keys(tc.args).length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">Arguments</p>
              <pre className="text-xs text-gray-300 bg-gray-800 rounded p-2 overflow-x-auto">
                {JSON.stringify(tc.args, null, 2)}
              </pre>
            </div>
          )}
          {/* Result */}
          {tc.preview !== undefined && (
            <div>
              <div className="flex items-center gap-1 mb-1">
                <Terminal size={11} className="text-gray-500" />
                <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">
                  Result{tc.lineCount && tc.lineCount > 20 ? ` (${tc.lineCount} lines, showing first 20)` : ''}
                </p>
              </div>
              <pre className="text-xs text-green-300 bg-gray-800 rounded p-2 overflow-x-auto max-h-60 whitespace-pre-wrap">
                {tc.preview}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
