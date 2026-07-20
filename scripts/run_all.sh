#!/usr/bin/env bash
# Start the load balancer and the RAG API together (local dev).
# Ollama itself must already be running (it starts automatically on macOS after
# `ollama pull`, or run `ollama serve`).
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Starting load balancer on :8080 ..."
uvicorn lb.balancer:app --host 127.0.0.1 --port 8080 &
LB_PID=$!

echo "Starting RAG API on :8000 ..."
uvicorn app.api:app --host 127.0.0.1 --port 8000 &
API_PID=$!

trap 'kill $LB_PID $API_PID 2>/dev/null || true' EXIT
echo "Both up. RAG API: http://127.0.0.1:8000/docs   |   LB health: http://127.0.0.1:8080/lb/health"
echo "Press Ctrl+C to stop."
wait
