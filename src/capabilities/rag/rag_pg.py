"""RAG with PostgreSQL array storage for vectors."""

import json
import numpy as np
from typing import Iterator
import psycopg
from sentence_transformers import SentenceTransformer

from .config import DB_NAME, EMBEDDING_MODEL, LLM_MODEL, CHUNK_SIZE
from .load_events import load_all_events, EventChunk
from modules.runtime.adapters.db import dsn_for


EMBED_DIM = 384


def ensure_vector_table(conn: psycopg.Connection):
    """Create vector table using PostgreSQL array (no extension needed)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rag_documents (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding FLOAT[],
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()


def clear_vector_store(conn: psycopg.Connection):
    """Clear all documents."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE rag_documents RESTART IDENTITY")
        conn.commit()


def get_embedding_model():
    """Get embedding model."""
    return SentenceTransformer(EMBEDDING_MODEL)


def get_llm():
    """Get LLM from Ollama."""
    import urllib.request
    
    def llm(prompt: str) -> str:
        url = "http://localhost:11434/api/generate"
        data = {"model": LLM_MODEL, "prompt": prompt, "stream": False}
        req = urllib.request.Request(
            url, data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")
    return llm


def index_documents(conn: psycopg.Connection, events: Iterator[EventChunk] = None, batch_size: int = 50):
    """Index documents into PostgreSQL array column."""
    embed_model = get_embedding_model()
    
    docs, metas, embeddings = [], [], []
    
    def flush():
        if not docs:
            return
        emb = embed_model.encode(docs).tolist()
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO rag_documents (content, metadata, embedding) VALUES (%s, %s, %s)",
                [(d, json.dumps(m), e) for d, m, e in zip(docs, metas, emb)]
            )
        conn.commit()
        docs.clear(); metas.clear(); embeddings.clear()

    if events:
        for event in events:
            docs.append(event.content)
            metas.append(event.metadata)
            if len(docs) >= batch_size:
                flush()
        flush()


def cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def similarity_search(conn: psycopg.Connection, query: str, k: int = 5) -> list[dict]:
    """Search similar documents using cosine similarity."""
    embed_model = get_embedding_model()
    query_emb = embed_model.encode([query])[0].tolist()

    with conn.cursor() as cur:
        cur.execute("SELECT id, content, metadata, embedding FROM rag_documents LIMIT 1000")
        rows = cur.fetchall()
    
    results = []
    for row in rows:
        sim = cosine_similarity(query_emb, row[3])
        results.append({
            "id": row[0],
            "content": row[1],
            "metadata": row[2],
            "similarity": sim,
        })
    
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:k]


def query_with_llm(similar_docs: list[dict], question: str) -> str:
    """Generate answer using LLM."""
    llm = get_llm()
    
    context = "\n\n".join([
        f"--- 文档 {i+1} ---\n{d['content']}"
        for i, d in enumerate(similar_docs)
    ])
    
    prompt = f"""基于以下参考资料，回答问题。如果资料中没有相关信息，请说明"根据已知信息无法回答"。

参考资料:
{context}

问题: {question}

回答:"""

    return llm(prompt)


def query_rag(question: str, k: int = 5) -> dict:
    """Complete RAG query."""
    conn = psycopg.connect(dsn_for(DB_NAME))
    try:
        similar_docs = similarity_search(conn, question, k)
        answer = query_with_llm(similar_docs, question)
        return {"answer": answer, "sources": similar_docs}
    finally:
        conn.close()


def build_index(clear_first: bool = False):
    """Build RAG index from events."""
    conn = psycopg.connect(dsn_for(DB_NAME))
    try:
        ensure_vector_table(conn)
        if clear_first:
            clear_vector_store(conn)
        
        events = load_all_events()
        index_documents(conn, events)
        print(f"RAG index built: indexed events from database")
    finally:
        conn.close()
