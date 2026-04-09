"""RAG module configuration."""

DB_NAME = "stock_event_mining"

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

LLM_MODEL = "qwen3:8b"
LLM_BASE_URL = "http://localhost:11434"
LLM_API_KEY = "ollama"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

VECTOR_STORE_DIR = "./rag_data"