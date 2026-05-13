# AI-Powered Kubernetes Troubleshooting Assistant

An agentic tool — with both a **web UI** and a **CLI** — that uses AI to diagnose and fix Kubernetes issues on any cluster (local Kind, remote EKS/GKE/AKS, bare-metal). Supports local Llama models via Ollama, AWS Bedrock Claude, and OpenAI GPT. Every troubleshooting session auto-generates a structured Markdown runbook.

---

## Features

| Feature | Details |
|---------|---------|
| **Web UI** | Real-time chat, cluster scan, runbook browser, settings — all in the browser |
| **CLI** | `chat`, `scan`, `fix`, `runbooks` commands for terminal use |
| **Multi-LLM** | Ollama (Llama 3.2, Mistral …), AWS Bedrock (Claude Sonnet/Opus), OpenAI (GPT-4o) |
| **Any cluster** | Works with any `~/.kube/config` context — Kind, EKS, GKE, AKS, K3s, bare-metal |
| **Agentic loop** | LLM calls 21 Kubernetes tools iteratively until the issue is diagnosed and fixed |
| **Safe by default** | Destructive actions always require confirmation (override with `--auto-fix`) |
| **Runbooks** | Every session writes a structured Markdown runbook + auto-updated index |
| **Persistent settings** | Settings saved in the UI are written back to `.env` and survive server restarts |

---

## Project Layout

```
.
├── main.py                        # CLI entry point
├── config.py                      # Settings (reads .env, persists UI changes back to .env)
├── setup.sh                       # One-shot environment setup
├── requirements.txt
├── .env.example                   # Copy to .env and fill in credentials
├── llm/                           # LLM provider abstraction
│   ├── base.py                    # Shared types: Message, ToolCall, LLMResponse
│   ├── ollama_provider.py
│   ├── bedrock_provider.py        # Bearer-token + IAM credential support
│   ├── openai_provider.py
│   └── factory.py
├── k8s/
│   ├── client.py                  # kubernetes-python wrapper
│   └── tools.py                   # 21 callable K8s tools
├── agents/
│   ├── tool_definitions.py        # JSON Schema exposed to the LLM
│   └── troubleshoot_agent.py      # Agentic loop with streaming event callbacks
├── runbook/
│   └── generator.py               # Markdown runbook + index writer
├── runbooks/                      # Generated runbooks (git-ignored)
└── web/
    ├── server.py                  # FastAPI backend (REST + WebSocket)
    ├── requirements-web.txt
    ├── start.sh                   # Start backend + frontend (dev or prod)
    └── frontend/                  # React + TypeScript + Tailwind SPA
        └── src/
            ├── App.tsx
            ├── types.ts
            ├── hooks/useWebSocket.ts
            └── components/
                ├── ChatView.tsx
                ├── ScanView.tsx
                ├── RunbooksView.tsx
                ├── SettingsView.tsx
                ├── MessageBubble.tsx
                ├── ToolCallCard.tsx
                └── ConfirmDialog.tsx
```

---

## Quick Start

### Web UI (recommended)

```bash
# 1. Set up the Python virtualenv
bash setup.sh

# 2. Configure credentials (or use the Settings page after starting)
cp .env.example .env

# 3. Start backend + frontend
bash web/start.sh          # dev mode — http://localhost:5173
bash web/start.sh prod     # production mode — http://localhost:8000
```

### CLI

```bash
source .venv/bin/activate

python main.py chat                                    # interactive REPL
python main.py scan                                    # full cluster scan
python main.py fix "nginx pods in CrashLoopBackOff"   # targeted fix
python main.py runbooks                                # list saved runbooks
```

---

## LLM Provider Setup

### Ollama — local, no API key needed

```bash
# Install: https://ollama.com
brew install ollama        # macOS
ollama pull llama3.2       # or: mistral, llama3.1, qwen2.5-coder

# .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

### AWS Bedrock — Claude Sonnet / Opus

Bedrock uses **Bearer-token API keys** (not the traditional Access Key + Secret pair).
Generate one in the AWS Console under **Amazon Bedrock → API keys**.

```bash
# .env
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Option A — Bedrock API key (Bearer token, recommended)
BEDROCK_API_KEY=<token from AWS Console → Bedrock → API keys>

# Option B — IAM long-term credentials (fallback)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Option C — IAM role / instance profile (no credentials needed in .env)
```

**Auth priority:** `BEDROCK_API_KEY` → `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` → default AWS credential chain (IAM role, `~/.aws/credentials`, …)

**Supported models** (cross-region inference profile IDs with `us.` prefix required):

| Model | ID |
|-------|----|
| Claude Sonnet 4.5 _(default)_ | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Claude Sonnet 4.6 | `us.anthropic.claude-sonnet-4-6` |
| Claude Opus 4.7 | `us.anthropic.claude-opus-4-7` |

> **Note:** Bare `anthropic.*` model IDs (without `us.`) fail with
> *"on-demand throughput isn't supported — retry with an inference profile"*.
> Always use the `us.*` prefixed IDs above.

### OpenAI

```bash
# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o        # or: gpt-4o-mini, o1-mini
```

---

## Web UI

The web UI streams the agent's reasoning and tool calls in real time.

### Chat

Type any Kubernetes issue in natural language. The agent will investigate, propose a fix, ask for confirmation before any destructive action, apply the fix, and verify it worked.

Special commands:
- Type **`scan`** to trigger a full cluster health scan from the chat input.

### Scan

One-click comprehensive scan across all namespaces. Shows a live activity log of every tool call, then an AI summary of all issues found. A runbook is generated automatically.

### Runbooks

Browse, read (rendered Markdown), and delete all previously generated runbooks.

### Settings

Configure everything without touching `.env` — settings are saved to `.env` immediately and persist across restarts.

| Setting | Options |
|---------|---------|
| LLM Provider | Ollama / AWS Bedrock / OpenAI |
| Bedrock model | Sonnet 4.5, Sonnet 4.6, Opus 4.7 (dropdown) |
| Bedrock API Key | Single Bearer-token field (masked, eye toggle) |
| OpenAI API Key | Masked field with eye toggle |
| Kubernetes context | Dropdown from `~/.kube/config` |
| Auto-fix | Toggle — skip confirmation prompts |
| Max log lines | Number of lines fetched per pod |

---

## How It Works

```
User (browser / CLI)
        │
        ▼
TroubleshootAgent ──► LLM  (Ollama · Bedrock · OpenAI)
        │                       │
        │   ◄── tool_calls ─────┘     (up to 30 iterations)
        │
        ▼
K8sTools — 21 tools
  Read-only
  ├── check_cluster_health    list_namespaces     get_pods
  ├── get_pod_logs            get_events          describe_pod
  ├── describe_node           get_nodes           get_deployments
  ├── get_services            get_pvcs            get_persistent_volumes
  ├── get_configmaps          get_resource_quotas run_kubectl
  │
  Mutating (require confirmation)
  ├── restart_deployment      rollback_deployment  scale_deployment
  ├── delete_pod              apply_manifest       patch_resource
        │
        ▼
RunbookGenerator
  runbooks/YYYYMMDD-HHMMSS-<slug>.md
  runbooks/index.md
```

**Web mode** streams every step over a WebSocket:
- `text` — AI reasoning chunks
- `tool_call` / `tool_result` — shown as collapsible cards in the UI
- `confirmation_required` — triggers a modal dialog before any mutating action
- `runbook` — notifies the UI when a new runbook is saved
- `done` — signals the end of the agent turn

**Argument sanitisation** — before every tool call, unknown keys and `null` values from the LLM are stripped so hallucinated parameters never cause runtime errors.

---

## Example Issues the Agent Handles

| Symptom | Agent workflow |
|---------|---------------|
| `CrashLoopBackOff` | Reads current + previous logs, events → finds crash reason → restarts or rolls back |
| `ImagePullBackOff` | Checks events → identifies wrong image tag or missing pull secret → proposes fix |
| `Pending pod` | Checks node conditions, resource quotas, PVCs, taints → finds scheduling blocker |
| `OOMKilled` | Gets resource limits + events → suggests raising memory limit → patches deployment |
| `Node NotReady` | Describes node → inspects conditions → cordons / proposes drain |
| `Rollout stuck` | Checks events + ReplicaSet → rolls back to last good revision |
| `PVC Pending` | Checks StorageClass, provisioner, events → diagnoses binding failure |
| General health check | Scans all namespaces → reports every issue with root cause and fix |

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` · `bedrock` · `openai` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Model name (must be pulled) |
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Cross-region inference profile ID |
| `BEDROCK_API_KEY` | — | Bearer token from AWS Console → Bedrock → API keys |
| `AWS_ACCESS_KEY_ID` | — | IAM Access Key (fallback if no Bearer token) |
| `AWS_SECRET_ACCESS_KEY` | — | IAM Secret Key (fallback if no Bearer token) |
| `AWS_SESSION_TOKEN` | — | STS / SSO session token (optional) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model |
| `KUBECONFIG` | `~/.kube/config` | Path to kubeconfig file |
| `K8S_CONTEXT` | _(current context)_ | Kubernetes context name |
| `AUTO_FIX` | `false` | Apply fixes without confirmation |
| `RUNBOOK_DIR` | `./runbooks` | Directory for generated runbooks |
| `MAX_LOG_LINES` | `200` | Lines fetched per pod log call |

---

## Requirements

- Python 3.11+
- `kubectl` on `$PATH`
- Valid `~/.kube/config` with cluster access
- One of:
  - **Ollama** running locally (`brew install ollama && ollama pull llama3.2`)
  - **AWS account** with Bedrock access and a Bedrock API key or IAM credentials
  - **OpenAI API key**
- Node.js 18+ (for the web UI frontend only)
