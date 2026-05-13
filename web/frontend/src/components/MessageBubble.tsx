import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, User, AlertCircle, Loader } from 'lucide-react'
import { ChatMessage } from '../types'
import { ToolCallCard } from './ToolCallCard'

export function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-gray-500 bg-gray-800 rounded-full px-3 py-1">
          {msg.content}
        </span>
      </div>
    )
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-4`}>
      {/* Avatar */}
      <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center
        ${isUser ? 'bg-blue-600' : 'bg-gray-700'}`}>
        {isUser
          ? <User size={15} className="text-white" />
          : <Bot size={15} className="text-cyan-400" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[85%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {isUser ? (
          <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
            {msg.content}
          </div>
        ) : (
          <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 min-w-0 w-full">
            {msg.isError ? (
              <div className="flex items-start gap-2 text-red-400">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <span className="text-sm">{msg.content}</span>
              </div>
            ) : (
              <>
                {msg.content && (
                  <div className="prose-k8s text-sm">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
                {msg.isStreaming && !msg.content && (
                  <Loader size={14} className="text-gray-400 animate-spin" />
                )}
              </>
            )}
            {msg.toolCalls.length > 0 && (
              <div className={`${msg.content ? 'mt-3' : ''} space-y-1`}>
                {msg.toolCalls.map(tc => (
                  <ToolCallCard key={tc.id} tc={tc} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
