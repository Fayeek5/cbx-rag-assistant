# Deploying free on Hugging Face Spaces

This is the recommended **zero-cost** way to get a public, working demo. A free
Hugging Face Space (Docker SDK, CPU basic) gives ~16 GB RAM — plenty to run the
full retrieval stack (embeddings + reranker). Generation uses **Groq's free API**
(OpenAI-compatible), so no local GPU or paid model is needed. No credit card.

## Cost: $0

| Piece | Where it runs | Cost |
|---|---|---|
| RAG API + retrieval (embeddings, Chroma, BM25, reranker) | HF Space (free CPU, 16 GB) | Free |
| Generation LLM | Groq API (`llama-3.1-8b-instant`) | Free tier |

The repo's `Dockerfile` already defaults `LLM_PROVIDER=openai` and the Groq base
URL — you only supply the API key as a Space secret.

## Steps

1. **Get a free Groq key:** sign in at <https://console.groq.com>, create an API
   key (starts with `gsk_...`). No card required.
2. **Create the Space:** on <https://huggingface.co>, **New → Space** → choose
   **Docker** as the SDK, blank template, **CPU basic (free)**.
3. **Get the code into the Space** (either way works):
   - Push this repo to the Space's git remote:
     ```bash
     git remote add space https://huggingface.co/spaces/<your-username>/cbx-rag-assistant
     git push space main
     ```
   - …or upload the files via the Space's web UI.
4. **Add the secret:** Space → **Settings → Variables and secrets** →
   **New secret** → name `OPENAI_API_KEY`, value = your Groq key.
   (Optional: override `LLM_MODEL` or `OPENAI_BASE_URL` there to use a different
   provider/model.)
5. The Space builds the image, seeds the vector store from `sample_docs/` on first
   boot, and serves on port 7860. When it's running, the chat UI is the Space URL.

## Notes

- **Storage is ephemeral** on free Spaces, so the vector store is re-seeded from
  `sample_docs/` on each cold start — fast for the small sample corpus, and
  self-healing. To demo your own content, change the ingest line in
  `scripts/serve.sh` to point at your docs.
- **Cold starts:** free Spaces sleep after inactivity and take ~30–60 s to wake
  and reload the embedding model. Fine for a demo.
- **Reranker stays on here** (there's enough RAM), so retrieval quality matches
  local.

## Alternative: Render (paid, persistent)

If you want a persistent disk and an always-on instance, use `render.yaml`
(see [`09-deploy-render.md`](09-deploy-render.md)). It needs the **standard**
plan (2 GB) to avoid out-of-memory on model load — the free/starter 512 MB tiers
are too small for the embedding model, which is why Hugging Face Spaces is the
better free option.
