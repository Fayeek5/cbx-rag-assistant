#!/usr/bin/env bash
# Start command for any host (Render, Hugging Face Spaces, Docker):
# seed the vector store once, then run the API on $PORT.
set -euo pipefail

CHROMA_DIR="${CHROMA_DIR:-./data/chroma_db}"
MARKER="${CHROMA_DIR}/.seeded"

# First boot only: ingest the sample docs so the demo has something to answer
# from. The marker lives on the persistent disk, so this runs once and survives
# restarts/redeploys. Point ingestion at your own docs here if you prefer.
if [ ! -f "$MARKER" ]; then
  echo "Seeding vector store from sample_docs/ ..."
  python scripts/ingest_docs.py sample_docs/ --reset
  mkdir -p "$CHROMA_DIR"
  touch "$MARKER"
fi

# Render provides $PORT; bind to 0.0.0.0 so the service is reachable.
exec uvicorn app.api:app --host 0.0.0.0 --port "${PORT:-10000}"
