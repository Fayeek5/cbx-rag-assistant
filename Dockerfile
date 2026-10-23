# Container image for the RAG API — works on Hugging Face Spaces (Docker SDK,
# free CPU tier, ~16 GB RAM) and any other container host.
#
# Generation uses a hosted OpenAI-compatible endpoint (Groq by default, free
# tier) since a local model can't run here. Set OPENAI_API_KEY as a secret in
# the host (never bake it into the image).
FROM python:3.12-slim

# Build tooling for a few wheels; removed afterwards to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Caches + data live under /app so the runtime user can always write them.
ENV HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers \
    CHROMA_DIR=/app/data/chroma_db \
    LLM_PROVIDER=openai \
    OPENAI_BASE_URL=https://api.groq.com/openai/v1 \
    LLM_MODEL=llama-3.1-8b-instant \
    PORT=7860 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/.cache && chmod -R 777 /app/data /app/.cache

EXPOSE 7860
CMD ["bash", "scripts/serve.sh"]
