#!/usr/bin/env bash
# One-liner start for the CBX RAG Assistant.
# Idempotent: starts Ollama (:11434), the load balancer (:8080), and the RAG API (:8000)
# only if they aren't already up, then waits for health and prints the URL.
#
#   ~/Projects/cbx-rag/scripts/start.sh
#
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

up() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# 1) Ollama (generation backend)
if up 11434; then echo "Ollama already running (:11434)"; else
  echo "Starting Ollama (:11434)..."; nohup ollama serve >/tmp/ollama_serve.log 2>&1 &
fi

# 2) venv
# shellcheck disable=SC1091
source .venv/bin/activate

# 3) Load balancer (:8080)
if up 8080; then echo "Load balancer already running (:8080)"; else
  echo "Starting load balancer (:8080)..."; nohup uvicorn lb.balancer:app --host 127.0.0.1 --port 8080 >/tmp/cbxrag_lb.log 2>&1 &
fi

# 4) RAG API (:8000)
if up 8000; then echo "RAG API already running (:8000)"; else
  echo "Starting RAG API (:8000)..."; nohup uvicorn app.api:app --host 127.0.0.1 --port 8000 >/tmp/cbxrag_api.log 2>&1 &
fi

# 5) wait for health (models load on first boot, ~15-30s)
printf "Waiting for RAG API health"
for _ in $(seq 1 40); do
  if curl -s -m 5 http://127.0.0.1:8000/health 2>/dev/null | grep -q '"status":"ok"'; then
    echo; echo "READY -> http://127.0.0.1:8000/"
    curl -s http://127.0.0.1:8000/health; echo
    echo "Docs: http://127.0.0.1:8000/docs   |   LB: http://127.0.0.1:8080/lb/health"
    exit 0
  fi
  printf "."; sleep 3
done
echo; echo "API did not report healthy in time. Check /tmp/cbxrag_api.log"
exit 1
