# AI-Powered Kubernetes Troubleshooting Assistant

> Full guide: [learnxops.com/project-ai-powered-kubernetes-troubleshooting-assistant](https://www.learnxops.com/project-ai-powered-kubernetes-troubleshooting-assistant/)

---

## Model Setup

Set `LLM_PROVIDER` in your `.env` to one of: `ollama`, `bedrock`, or `openai`.

**Ollama (local, no API key)**
```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

**AWS Bedrock**
```env
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Option 1 — Bearer token (recommended)
BEDROCK_API_KEY=<your-bedrock-api-key>

# Option 2 — IAM credentials
AWS_ACCESS_KEY_ID=<key-id>
AWS_SECRET_ACCESS_KEY=<secret>
# Option 3 — default AWS credential chain (~/.aws/credentials, IAM role, etc.)
```

**OpenAI**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_MODEL=gpt-4o
```

---

## Web Setup

```bash
# 1. Set up the Python virtual environment
./setup.sh

# 2. Configure credentials (or use the Settings page after starting)
cp .env.example .env

# 3. Start backend + frontend
bash web/start.sh        # dev mode   → http://localhost:5173
bash web/start.sh prod   # prod mode  → http://localhost:8000
```

---

## CLI Usage

```bash
source .venv/bin/activate

python main.py chat                                    # interactive REPL
python main.py scan                                    # full cluster scan
python main.py fix "nginx pods in CrashLoopBackOff"   # targeted fix
python main.py runbooks                                # list saved runbooks
```
