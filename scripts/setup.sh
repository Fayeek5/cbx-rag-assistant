#!/usr/bin/env bash
# One-time local setup for the cbx-rag stack.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> 1/4 Python virtual environment"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 2/4 Python dependencies"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "==> 3/4 .env file"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from .env.example"
fi

echo "==> 4/4 Ollama model (generation LLM)"
if command -v ollama >/dev/null 2>&1; then
  ollama pull qwen2.5:7b
else
  echo "    Ollama not found. Install it from https://ollama.com/download"
  echo "    then run:  ollama pull qwen2.5:7b"
fi

echo
echo "Setup complete. Next:"
echo "  source .venv/bin/activate"
echo "  python scripts/ingest_docs.py sample_docs/"
echo "  ./scripts/run_all.sh      # starts Ollama LB + RAG API"
