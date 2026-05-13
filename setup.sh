#!/usr/bin/env bash
set -euo pipefail

echo "=== AI-Powered Kubernetes Troubleshooting Assistant — Setup ==="

# Create virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy .env if not present
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  Created .env from .env.example"
    echo "  Edit .env to set your LLM_PROVIDER and credentials."
fi

mkdir -p runbooks

echo ""
echo "Setup complete. Activate the venv and run the assistant:"
echo ""
echo "  source .venv/bin/activate"
echo "  python main.py chat            # interactive mode"
echo "  python main.py scan            # automated cluster scan"
echo "  python main.py fix 'pods crash after latest deploy'  # targeted fix"
echo "  python main.py runbooks        # list generated runbooks"
echo ""
echo "Quick provider examples:"
echo "  python main.py chat --provider ollama  --model llama3.2"
echo "  python main.py chat --provider bedrock --model anthropic.claude-3-5-sonnet-20241022-v2:0"
echo "  python main.py chat --provider openai  --model gpt-4o"
