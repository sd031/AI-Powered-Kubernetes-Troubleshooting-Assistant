export type Tab = 'chat' | 'scan' | 'runbooks' | 'settings'

// ─── WebSocket event types (server → client) ──────────────────────────────────

export interface TextEvent       { type: 'text';                  content: string }
export interface ToolCallEvent   { type: 'tool_call';  id: string; name: string; args: Record<string, unknown> }
export interface ToolResultEvent { type: 'tool_result'; id: string; name: string; preview: string; line_count: number }
export interface ConfirmEvent    { type: 'confirmation_required'; id: string; action: string }
export interface RunbookEvent    { type: 'runbook';    path: string; filename: string }
export interface DoneEvent       { type: 'done' }
export interface ErrorEvent      { type: 'error';      message: string }
export interface StatusEvent     { type: 'status';     message: string }
export interface ProviderEvent   { type: 'provider_info'; provider: string; model: string; context: string; k8s_version: string }
export interface ResetAckEvent   { type: 'reset_ack' }

export type AgentEvent =
  | TextEvent | ToolCallEvent | ToolResultEvent | ConfirmEvent
  | RunbookEvent | DoneEvent | ErrorEvent | StatusEvent
  | ProviderEvent | ResetAckEvent

// ─── UI message model ─────────────────────────────────────────────────────────

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ToolCallRecord {
  id: string
  name: string
  args: Record<string, unknown>
  preview?: string
  lineCount?: number
  done: boolean
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  toolCalls: ToolCallRecord[]
  isStreaming: boolean
  isError: boolean
}

// ─── Runbook ──────────────────────────────────────────────────────────────────

export interface RunbookMeta {
  filename: string
  title: string
  date: string
  size: number
}

// ─── Config ───────────────────────────────────────────────────────────────────

export interface AppConfig {
  llm_provider: string
  ollama_host: string
  ollama_model: string
  // Bedrock
  bedrock_model_id: string
  aws_region: string
  bedrock_api_key_configured: boolean
  aws_session_token_configured: boolean
  // OpenAI
  openai_model: string
  openai_api_key_configured: boolean
  // Common
  k8s_context: string
  auto_fix: boolean
  max_log_lines: number
  runbook_dir: string
}

export interface ProviderInfo {
  provider: string
  model: string
  context: string
  k8s_version: string
}
