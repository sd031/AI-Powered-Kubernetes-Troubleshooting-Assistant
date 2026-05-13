import { ShieldAlert } from 'lucide-react'

interface Props {
  action: string
  onAnswer: (yes: boolean) => void
}

export function ConfirmDialog({ action, onAnswer }: Props) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-red-700 rounded-xl shadow-2xl max-w-lg w-full p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-red-900/50 rounded-full flex items-center justify-center shrink-0">
            <ShieldAlert size={20} className="text-red-400" />
          </div>
          <div>
            <h3 className="text-white font-semibold text-base">Confirmation Required</h3>
            <p className="text-gray-400 text-xs">This action will modify cluster state</p>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 mb-5 border border-gray-700">
          <p className="text-yellow-300 text-sm font-mono leading-relaxed">{action}</p>
        </div>

        <div className="flex gap-3 justify-end">
          <button
            onClick={() => onAnswer(false)}
            className="px-4 py-2 rounded-lg border border-gray-600 text-gray-300
                       hover:bg-gray-800 hover:text-white transition-colors text-sm font-medium"
          >
            No, cancel
          </button>
          <button
            onClick={() => onAnswer(true)}
            className="px-4 py-2 rounded-lg bg-red-600 text-white
                       hover:bg-red-500 transition-colors text-sm font-medium"
          >
            Yes, proceed
          </button>
        </div>
      </div>
    </div>
  )
}
