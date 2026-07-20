"""Central configuration.

All tunables live here and are overridable via environment variables (loaded
from a local .env file). Import `settings` anywhere in the app.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Embedding model (Hugging Face id)
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Vector store
    chroma_dir: str = "./data/chroma_db"
    collection_name: str = "cbx_docs"

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 120

    # Retrieval
    top_k: int = 5

    # Conversation memory — how many prior turns to remember per session
    history_turns: int = 6

    # Generation
    llm_model: str = "qwen2.5:7b"
    lb_url: str = "http://127.0.0.1:8080"

    # Load balancer backends (comma-separated env -> list)
    ollama_backends: str = "http://127.0.0.1:11434"

    # Servers
    rag_api_host: str = "127.0.0.1"
    rag_api_port: int = 8000
    lb_host: str = "127.0.0.1"
    lb_port: int = 8080

    @property
    def backend_list(self) -> list[str]:
        return [b.strip() for b in self.ollama_backends.split(",") if b.strip()]


settings = Settings()
