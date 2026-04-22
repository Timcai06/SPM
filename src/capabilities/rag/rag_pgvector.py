"""RAG with pgvector storage."""

from typing import Iterator, Optional
from dataclasses import dataclass
import numpy as np

import psycopg

from .config import DB_NAME, EMBEDDING_MODEL, LLM_MODEL, LLM_BASE_URL, CHUNK_SIZE, VECTOR_TABLE, VECTOR_DIM
from .load_events import load_all_events, EventChunk
from .load_pdfs import load_pdf, PDFChunk
from modules.runtime.adapters.db import dsn_for


@dataclass
class Document:
    content: str
    metadata: dict


def get_embedding_model():
    """Get embedding model from sentence-transformers."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL)


def get_llm():
    """Get LLM from Ollama via LangChain."""
    from langchain_community.llms import Ollama
    return Ollama(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
    )


def ensure_vector_table(conn: psycopg.Connection):
    """Create vector table if not exists."""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {VECTOR_TABLE} (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector({VECTOR_DIM})
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {VECTOR_TABLE}_idx 
            ON {VECTOR_TABLE} 
            USING ivfflat (embedding vector_l2_ops)
            WITH (lists = 100)
        """)
        conn.commit()


def clear_vector_store(conn: psycopg.Connection):
    """Clear all documents from vector store."""
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {VECTOR_TABLE} RESTART IDENTITY")
        conn.commit()


def index_documents(
    conn: psycopg.Connection,
    events: Iterator[EventChunk] = None,
    pdfs: Iterator[PDFChunk] = None,
    batch_size: int = 100,
):
    """Index documents into pgvector."""
    embed_model = get_embedding_model()
    
    docs = []
    metas = []
    embeddings = []

    def flush():
        if not docs:
            return
        with conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO {VECTOR_TABLE} (content, metadata, embedding) VALUES (%s, %s, %s)",
                [(d, m, e.tolist()) for d, m, e in zip(docs, metas, embeddings)]
            )
        conn.commit()
        docs.clear()
        metas.clear()
        embeddings.clear()

    if events:
        for event in events:
            docs.append(event.content)
            metas.append(event.metadata)
            if len(docs) >= batch_size:
                emb = embed_model.encode(docs)
                embeddings.extend(emb)
                flush()

    if pdfs:
        for pdf in pdfs:
            docs.append(pdf.content)
            metas.append(pdf.metadata)
            if len(docs) >= batch_size:
                emb = embed_model.encode(docs)
                embeddings.extend(emb)
                flush()

    if docs:
        emb = embed_model.encode(docs)
        embeddings.extend(emb)
        flush()


def similarity_search(
    conn: psycopg.Connection,
    query: str,
    k: int = 5,
) -> list[dict]:
    """Search similar documents."""
    embed_model = get_embedding_model()
    query_emb = embed_model.encode([query])[0].tolist()

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT content, metadata, 1 - (embedding <=> %s::vector) as similarity
            FROM {VECTOR_TABLE}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_emb, query_emb, k)
        )
        results = []
        for row in cur:
            results.append({
                "content": row[0],
                "metadata": row[1],
                "similarity": row[2],
            })
    return results


def query_with_llm(similar_docs: list[dict], question: str) -> str:
    """Generate answer using LLM with retrieved docs as context."""
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

    return llm.invoke(prompt)


def query_rag(conn: psycopg.Connection, question: str, k: int = 5) -> dict:
    """Complete RAG query: retrieve + generate."""
    similar_docs = similarity_search(conn, question, k)
    answer = query_with_llm(similar_docs, question)
    return {
        "answer": answer,
        "sources": similar_docs,
    }


def build_index(
    events: bool = True,
    pdf_dir: str = None,
    clear_first: bool = False,
):
    """Build RAG index from data sources."""
    conn = psycopg.connect(dsn_for(DB_NAME))
    try:
        ensure_vector_table(conn)
        if clear_first:
            clear_vector_store(conn)
        
        event_iter = load_all_events() if events else None
        pdf_iter = load_pdf(pdf_dir, CHUNK_SIZE) if pdf_dir else None
        
        index_documents(conn, event_iter, pdf_iter)
        print("RAG index built successfully")
    finally:
        conn.close()
