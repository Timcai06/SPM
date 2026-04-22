"""Minimal RAG using Ollama directly (no heavy dependencies)."""

import json
from typing import Iterator
import psycopg

from .config import DB_NAME, LLM_MODEL
from .load_events import load_all_events
from modules.runtime.adapters.db import dsn_for


def get_llm_response(prompt: str) -> str:
    """Get LLM response from Ollama."""
    import urllib.request
    import urllib.error
    
    url = "http://localhost:11434/api/generate"
    data = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "")
    except urllib.error.URLError as e:
        return f"Error: {e}"


def search_events(keywords: str, limit: int = 5) -> list[dict]:
    """Search events by keywords (simple text match)."""
    conn = psycopg.connect(dsn_for(DB_NAME))
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    e.id,
                    e.event_name,
                    e.event_summary,
                    e.event_date,
                    e.sentiment,
                    e.industry_type,
                    COALESCE(string_agg(DISTINCT c.company_name, ', '), '') as companies
                FROM structured_events e
                LEFT JOIN event_company_links ecl ON ecl.structured_event_id = e.id
                LEFT JOIN companies c ON c.id = ecl.company_id
                WHERE e.event_name ILIKE %s OR e.event_summary ILIKE %s
                GROUP BY e.id
                ORDER BY e.event_date DESC
                LIMIT %s
            """, (f"%{keywords}%", f"%{keywords}%", limit))
            
            results = []
            for row in cur:
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "date": row[3],
                    "category": row[4],
                    "industry": row[5],
                    "companies": row[6],
                })
            return results
    finally:
        conn.close()


def query_rag(question: str, k: int = 5) -> dict:
    """Query RAG system with simple retrieval + LLM."""
    events = search_events(question.split()[-1] if question.split() else question, k)
    
    context = "\n\n".join([
        f"--- 事件 {i+1} ---\n标题: {e['title']}\n时间: {e['date']}\n行业: {e.get('industry', '')}\n情感: {e['category']}\n关联公司: {e['companies']}\n内容: {e['content'][:300]}..."
        for i, e in enumerate(events)
    ])
    
    prompt = f"""基于以下事件信息回答问题。如果信息不足，请说明。

事件信息:
{context}

问题: {question}

回答:"""

    answer = get_llm_response(prompt)
    
    return {
        "answer": answer,
        "sources": events,
    }


def build_index():
    """Build index is not needed - we use direct DB search."""
    print("Using direct database search (no indexing needed)")


if __name__ == "__main__":
    result = query_rag("新能源 政策")
    print(result["answer"])
    print("\nSources:", len(result["sources"]))
