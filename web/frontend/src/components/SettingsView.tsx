import { useEffect, useState } from 'react'
import { Save, RefreshCw, CheckCircle, Eye, EyeOff, Lock, AlertCircle } from 'lucide-react'
import { AppConfig } from '../types'

// Cross-region inference profile IDs (us.*) are required for on-demand invocation
const BEDROCK_MODELS = [
  { id: 'us.anthropic.claude-sonnet-4-5-20250929-v1:0', label: 'Claude Sonnet 4.5' },
  { id: 'us.anthropic.claude-sonnet-4-6',               label: 'Claude Sonnet 4.6' },
  { id: 'us.anthropic.claude-opus-4-7',                 label: 'Claude Opus 4.7' },
]

const PROVIDERS = [
  { id: 'ollama',  label: 'Ollama (Local)', desc: 'Run Llama, Mistral, Qwen etc. locally via Ollama — no API key needed' },
  { id: 'bedrock', label: 'AWS Bedrock',    desc: 'Claude Sonnet 3.5 via Amazon Bedrock — requires AWS credentials' },
  { id: 'openai',  label: 'OpenAI',         desc: 'GPT-4o and other OpenAI models — requires an API key' },
]

/** Credential values the user types — kept separate so they are never echoed back. */
interface NewCreds {
  bedrock_api_key: string   // combined "ACCESS_KEY_ID:SECRET_ACCESS_KEY"
  aws_session_token: string
  openai_api_key: string
}

export function SettingsView({ onSave }: { onSave: () => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [creds, setCreds] = useState<NewCreds>({
    bedrock_api_key: '',
    aws_session_token: '',
    openai_api_key: '',
  })
  const [contexts, setContexts] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      fetch('/api/config').then(r => r.json()),
      fetch('/api/cluster/contexts').then(r => r.json()),
    ]).then(([cfg, ctxs]) => {
      setConfig(cfg)
      setContexts(ctxs.contexts ?? [])
    }).catch(() => setError('Failed to load configuration from backend.'))
      .finally(() => setLoading(false))
  }, [])

  const update = (patch: Partial<AppConfig>) =>
    setConfig(c => c ? { ...c, ...patch } : c)

  const updateCred = (patch: Partial<NewCreds>) =>
    setCreds(c => ({ ...c, ...patch }))

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    setError('')
    try {
      const body: Record<string, unknown> = {
        llm_provider:    config.llm_provider,
        ollama_model:    config.ollama_model,
        bedrock_model_id: config.bedrock_model_id,
        aws_region:      config.aws_region,
        openai_model:    config.openai_model,
        k8s_context:     config.k8s_context,
        auto_fix:        config.auto_fix,
        max_log_lines:   config.max_log_lines,
      }
      // Only include credential fields if the user actually typed something
      if (creds.bedrock_api_key)  body.bedrock_api_key  = creds.bedrock_api_key
      if (creds.aws_session_token) body.aws_session_token = creds.aws_session_token
      if (creds.openai_api_key)   body.openai_api_key   = creds.openai_api_key

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await res.text())

      // Clear typed credentials after successful save
      setCreds({ bedrock_api_key: '', aws_session_token: '', openai_api_key: '' })
      // Refresh configured flags from server
      const refreshed = await fetch('/api/config').then(r => r.json())
      setConfig(refreshed)

      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
      onSave()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading || !config) return (
    <div className="flex items-center justify-center h-full gap-2 text-gray-500">
      <RefreshCw size={16} className="animate-spin" /> Loading config…
    </div>
  )

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 shrink-0">
        <h2 className="font-semibold text-white">Settings</h2>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 text-white
                     text-sm hover:bg-blue-500 disabled:opacity-50 transition-colors font-medium"
        >
          {saved
            ? <><CheckCircle size={14} /> Saved</>
            : saving
            ? <><RefreshCw size={14} className="animate-spin" /> Saving…</>
            : <><Save size={14} /> Save</>}
        </button>
      </div>

      {error && (
        <div className="mx-4 mt-3 flex items-center gap-2 p-3 bg-red-900/30 border border-red-700
                        rounded-lg text-sm text-red-300">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6 max-w-2xl mx-auto w-full space-y-8">

        {/* ── LLM Provider ──────────────────────────────────────────────── */}
        <section>
          <SectionTitle>LLM Provider</SectionTitle>
          <div className="space-y-2">
            {PROVIDERS.map(p => {
              const active = config.llm_provider === p.id
              return (
                <label
                  key={p.id}
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors
                    ${active
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'border-gray-700 bg-gray-800 hover:border-gray-600'}`}
                >
                  <input
                    type="radio"
                    name="provider"
                    value={p.id}
                    checked={active}
                    onChange={() => update({ llm_provider: p.id })}
                    className="mt-0.5 accent-blue-500 shrink-0"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-100">{p.label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{p.desc}</p>
                  </div>
                </label>
              )
            })}
          </div>
        </section>

        {/* ── Ollama ────────────────────────────────────────────────────── */}
        {config.llm_provider === 'ollama' && (
          <section>
            <SectionTitle>Ollama Model</SectionTitle>
            <Field
              value={config.ollama_model}
              onChange={v => update({ ollama_model: v })}
              placeholder="llama3.2"
              hint="Model must be pulled first: ollama pull llama3.2"
            />
          </section>
        )}

        {/* ── AWS Bedrock ───────────────────────────────────────────────── */}
        {config.llm_provider === 'bedrock' && (
          <section className="space-y-4">
            <SectionTitle>AWS Bedrock Settings</SectionTitle>

            <div className="p-3 bg-amber-900/20 border border-amber-700/50 rounded-lg text-xs text-amber-300 flex items-start gap-2">
              <Lock size={12} className="shrink-0 mt-0.5" />
              The Bedrock API Key is a Bearer token generated from the AWS Console under
              {' '}<span className="font-mono">Bedrock → API keys</span>.
              It is stored in server memory only and never returned to the browser.
              You can also set <code className="font-mono">BEDROCK_API_KEY</code> in <code className="font-mono">.env</code>.
            </div>

            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Model</label>
                <select
                  value={config.bedrock_model_id}
                  onChange={e => update({ bedrock_model_id: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                             text-sm text-gray-100 focus:outline-none focus:border-blue-500"
                >
                  {BEDROCK_MODELS.map(m => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">AWS Region</label>
                <Field
                  value={config.aws_region}
                  onChange={v => update({ aws_region: v })}
                  placeholder="us-east-1"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">
                  Bedrock API Key
                  {config.bedrock_api_key_configured && <ConfiguredBadge />}
                </label>
                <SecretField
                  value={creds.bedrock_api_key}
                  onChange={v => updateCred({ bedrock_api_key: v })}
                  placeholder={
                    config.bedrock_api_key_configured
                      ? '••••••••  (configured — enter new to replace)'
                      : 'Paste Bearer token from AWS Console → Bedrock → API keys'
                  }
                  autoComplete="new-password"
                />
                <p className="text-xs text-gray-600 mt-1">
                  Generate in <span className="text-gray-500">AWS Console → Amazon Bedrock → API keys</span>.
                  Short-term: expires in ≤ 12 h · Long-term: expires on a configured date.
                  Leave blank to fall back to <span className="font-mono text-gray-500">AWS_ACCESS_KEY_ID</span> + <span className="font-mono text-gray-500">AWS_SECRET_ACCESS_KEY</span> from <span className="font-mono text-gray-500">.env</span> or IAM role.
                </p>
              </div>
            </div>
          </section>
        )}

        {/* ── OpenAI ────────────────────────────────────────────────────── */}
        {config.llm_provider === 'openai' && (
          <section className="space-y-4">
            <SectionTitle>OpenAI Settings</SectionTitle>

            <div className="p-3 bg-amber-900/20 border border-amber-700/50 rounded-lg text-xs text-amber-300 flex items-start gap-2">
              <Lock size={12} className="shrink-0 mt-0.5" />
              API key is stored in server memory only and never returned to the browser.
              Leave blank to keep the existing value.
            </div>

            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Model</label>
                <Field
                  value={config.openai_model}
                  onChange={v => update({ openai_model: v })}
                  placeholder="gpt-4o"
                  hint="Other options: gpt-4o-mini, gpt-4-turbo, o1-mini"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">
                  API Key
                  {config.openai_api_key_configured && <ConfiguredBadge />}
                </label>
                <SecretField
                  value={creds.openai_api_key}
                  onChange={v => updateCred({ openai_api_key: v })}
                  placeholder={config.openai_api_key_configured ? '••••••••  (configured — enter new to replace)' : 'sk-…'}
                  autoComplete="new-password"
                />
                <p className="text-xs text-gray-600 mt-1">
                  Get your key at <span className="text-gray-500">platform.openai.com/api-keys</span>
                </p>
              </div>
            </div>
          </section>
        )}

        {/* ── Kubernetes ────────────────────────────────────────────────── */}
        <section>
          <SectionTitle>Kubernetes Context</SectionTitle>
          {contexts.length > 0 ? (
            <select
              value={config.k8s_context}
              onChange={e => update({ k8s_context: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                         text-sm text-gray-100 focus:outline-none focus:border-blue-500"
            >
              <option value="">(current context)</option>
              {contexts.map(ctx => (
                <option key={ctx} value={ctx}>{ctx}</option>
              ))}
            </select>
          ) : (
            <Field
              value={config.k8s_context}
              onChange={v => update({ k8s_context: v })}
              placeholder="(current context)"
              hint="Context name from ~/.kube/config"
            />
          )}
        </section>

        {/* ── Behaviour ─────────────────────────────────────────────────── */}
        <section>
          <SectionTitle>Behaviour</SectionTitle>
          <div className="space-y-3">
            <label className="flex items-center justify-between p-3 bg-gray-800 rounded-xl border border-gray-700 cursor-pointer">
              <div>
                <p className="text-sm text-gray-200 font-medium">Auto-fix</p>
                <p className="text-xs text-gray-500 mt-0.5">Apply fixes without confirmation prompts</p>
              </div>
              <Toggle checked={config.auto_fix} onChange={v => update({ auto_fix: v })} />
            </label>

            <div className="flex items-center justify-between p-3 bg-gray-800 rounded-xl border border-gray-700">
              <div>
                <p className="text-sm text-gray-200 font-medium">Max log lines</p>
                <p className="text-xs text-gray-500 mt-0.5">Lines fetched per pod log request</p>
              </div>
              <input
                type="number"
                value={config.max_log_lines}
                onChange={e => update({ max_log_lines: parseInt(e.target.value) || 200 })}
                min={10} max={2000}
                className="w-20 bg-gray-700 border border-gray-600 rounded-lg px-2 py-1
                           text-sm text-right text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </section>

        {/* ── Info ──────────────────────────────────────────────────────── */}
        <section>
          <SectionTitle>Info</SectionTitle>
          <div className="p-3 bg-gray-800 rounded-xl border border-gray-700 text-xs text-gray-500 font-mono space-y-1">
            <p>Runbooks directory: {config.runbook_dir}</p>
            <p className="text-gray-600 pt-1">
              Settings saved here apply immediately (existing .env is not modified).
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
      {children}
    </h3>
  )
}

function ConfiguredBadge() {
  return (
    <span className="ml-2 inline-flex items-center gap-1 text-xs bg-green-900/40 text-green-400
                     border border-green-700/50 rounded-full px-1.5 py-0.5 font-sans">
      <CheckCircle size={10} /> configured
    </span>
  )
}

function Field({ value, onChange, placeholder, hint }: {
  value: string
  onChange: (v: string) => void
  placeholder: string
  hint?: string
}) {
  return (
    <div>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                   text-sm text-gray-100 placeholder-gray-600
                   focus:outline-none focus:border-blue-500 transition-colors"
      />
      {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
    </div>
  )
}

function SecretField({ value, onChange, placeholder, autoComplete }: {
  value: string
  onChange: (v: string) => void
  placeholder: string
  autoComplete?: string
}) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 pr-10
                   text-sm text-gray-100 placeholder-gray-600 font-mono
                   focus:outline-none focus:border-blue-500 transition-colors"
      />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        tabIndex={-1}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
        title={visible ? 'Hide' : 'Show'}
      >
        {visible ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors
        ${checked ? 'bg-blue-600' : 'bg-gray-600'}`}
    >
      <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform
        mt-0.5 ${checked ? 'translate-x-4' : 'translate-x-0.5'}`} />
    </button>
  )
}
