# AI-Powered Kubernetes Troubleshooting Assistant

> Full guide: [learnxops.com/project-ai-powered-kubernetes-troubleshooting-assistant](https://www.learnxops.com/project-ai-powered-kubernetes-troubleshooting-assistant/)

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
