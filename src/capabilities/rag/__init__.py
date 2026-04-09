"""RAG module for stock events."""

from .config import DB_NAME
from .load_events import load_all_events
from .rag_minimal import build_index, query_rag