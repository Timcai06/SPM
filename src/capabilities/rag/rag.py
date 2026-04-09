"""Vector store and RAG chain."""

from typing import Iterator, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import psycopg

from .config import DB_NAME, EMBEDDING_MODEL, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, CHUNK_SIZE, CHUNK_OVERLAP
from .load_events import load_all_events, EventChunk
from .load_pdfs import load_pdf, PDFChunk


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


def create_chroma_store(persist_dir: str = "./rag_data"):
    """Create Chroma vector store."""
    import chromadb
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    chroma_client = chromadb.PersistentClient(path=persist_dir)
    
    return Chroma(
        client=chroma_client,
        collection_name="stock_rag",
        embedding_function=embeddings,
    )


def index_documents(
    vector_store,
    events: Iterator[EventChunk] = None,
    pdfs: Iterator[PDFChunk] = None,
):
    """Index documents into vector store."""
    docs = []
    metadatas = []

    if events:
        for event in events:
            docs.append(event.content)
            metadatas.append(event.metadata)

    if pdfs:
        for pdf in pdfs:
            docs.append(pdf.content)
            metadatas.append(pdf.metadata)

    if docs:
        vector_store.add_texts(texts=docs, metadatas=metadatas)


def create_rag_chain(vector_store):
    """Create RAG chain with retrieval + LLM."""
    from langchain.chains import RetrievalQA

    retriever = vector_store.as_retriever(search_kwargs={"k": 5})
    llm = get_llm()

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
    )


def query_rag(chain, question: str) -> dict:
    """Query RAG system."""
    result = chain.invoke({"query": question})
    return {
        "answer": result["result"],
        "sources": [
            {"content": doc.page_content[:200], "metadata": doc.metadata}
            for doc in result.get("source_documents", [])
        ],
    }


def init_vector_store(
    persist_dir: str = "./rag_data",
    events: bool = True,
    pdf_dir: str = None,
) -> any:
    """Initialize vector store with documents."""
    vector_store = create_chroma_store(persist_dir)
    
    event_iter = load_all_events() if events else None
    pdf_iter = None
    if pdf_dir:
        pdf_iter = load_pdf(pdf_dir, CHUNK_SIZE)

    index_documents(vector_store, event_iter, pdf_iter)
    return vector_store


def build_rag(
    persist_dir: str = "./rag_data",
    pdf_dir: str = None,
) -> any:
    """Build complete RAG system."""
    vector_store = init_vector_store(persist_dir, events=True, pdf_dir=pdf_dir)
    return create_rag_chain(vector_store)