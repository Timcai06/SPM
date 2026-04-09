"""RAG with Chroma vector store (no pgvector required)."""

from typing import Iterator, Optional
from dataclasses import dataclass

import numpy as np

from .config import DB_NAME, EMBEDDING_MODEL, LLM_MODEL, LLM_BASE_URL, CHUNK_SIZE, VECTOR_STORE_DIR
from .load_events import load_all_events, EventChunk
from .load_pdfs import load_pdf, PDFChunk


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


def create_chroma_store(persist_dir: str = VECTOR_STORE_DIR):
    """Create Chroma vector store."""
    import chromadb
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    chroma_client = chromadb.PersistentClient(path=persist_dir)
    
    return Chroma(
        client=chroma_client,
        collection_name="stock_events",
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


def query_rag(question: str, k: int = 5) -> dict:
    """Query RAG system."""
    vector_store = create_chroma_store()
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    llm = get_llm()
    
    from langchain.chains import RetrievalQA
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
    )
    
    result = chain.invoke({"query": question})
    return {
        "answer": result["result"],
        "sources": [
            {"content": doc.page_content, "metadata": doc.metadata}
            for doc in result.get("source_documents", [])
        ],
    }


def build_index(
    events: bool = True,
    pdf_dir: str = None,
    clear_first: bool = False,
):
    """Build RAG index from data sources."""
    import chromadb
    
    if clear_first:
        chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)
        chroma_client.delete_collection("stock_events")
    
    vector_store = create_chroma_store()
    
    event_iter = load_all_events() if events else None
    pdf_iter = load_pdf(pdf_dir, CHUNK_SIZE) if pdf_dir else None
    
    index_documents(vector_store, event_iter, pdf_iter)
    print("RAG index built successfully")