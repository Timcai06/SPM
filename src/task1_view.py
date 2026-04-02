#!/usr/bin/env python3
"""Simple Streamlit viewer for Task 1 PostgreSQL tables."""

from __future__ import annotations

import pandas as pd
import psycopg
import streamlit as st


DEFAULT_DB = "stock_event_mining"


def get_connection(db_name: str):
    return psycopg.connect(f"dbname={db_name} user=tim host=127.0.0.1 port=5432")


def load_dataframe(conn, query: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        rows = cur.fetchall()
        cols = [desc.name for desc in cur.description]
    return pd.DataFrame(rows, columns=cols)


def main() -> None:
    st.set_page_config(page_title="Task 1 Data Viewer", layout="wide")
    st.title("Task 1 Data Viewer")

    db_name = st.sidebar.text_input("Database", DEFAULT_DB)
    limit = st.sidebar.slider("Rows per table", min_value=10, max_value=200, value=50, step=10)
    subject_filter = st.sidebar.text_input("Event Subject Type")
    industry_filter = st.sidebar.text_input("Industry Type")

    try:
        conn = get_connection(db_name)
    except Exception as exc:
        st.error(f"Database connection failed: {exc}")
        return

    with conn:
        summary = load_dataframe(
            conn,
            """
            SELECT 'raw_documents' AS table_name, count(*) AS row_count FROM raw_documents
            UNION ALL
            SELECT 'event_candidates', count(*) FROM event_candidates
            UNION ALL
            SELECT 'structured_events', count(*) FROM structured_events
            UNION ALL
            SELECT 'companies', count(*) FROM companies
            UNION ALL
            SELECT 'event_company_links', count(*) FROM event_company_links
            """
        )
        st.subheader("Summary")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        st.subheader("Raw Documents")
        raw_docs = load_dataframe(
            conn,
            """
            SELECT id, source, publish_time, title, url
            FROM raw_documents
            ORDER BY publish_time DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        st.dataframe(raw_docs, use_container_width=True, hide_index=True)

        st.subheader("Event Candidates")
        candidates = load_dataframe(
            conn,
            """
            SELECT c.id, d.source, d.publish_time, c.is_event, c.filter_reason, c.score_hint, d.title
            FROM event_candidates c
            JOIN raw_documents d ON d.id = c.raw_document_id
            ORDER BY d.publish_time DESC, c.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        st.dataframe(candidates, use_container_width=True, hide_index=True)

        st.subheader("Structured Events")
        conditions = []
        params = []
        if subject_filter:
            conditions.append("event_subject_type = %s")
            params.append(subject_filter)
        if industry_filter:
            conditions.append("industry_type = %s")
            params.append(industry_filter)
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        events = load_dataframe(
            conn,
            f"""
            SELECT id, event_id, event_date, source, event_subject_type, industry_type,
                   sentiment, heat_score, intensity_score, impact_scope, event_name
            FROM structured_events
            {where_sql}
            ORDER BY event_date DESC, id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        st.dataframe(events, use_container_width=True, hide_index=True)

        st.subheader("Companies")
        companies = load_dataframe(
            conn,
            """
            SELECT id, ts_code, company_name, exchange, industry_l1, industry_l2, is_active
            FROM companies
            ORDER BY id DESC
            LIMIT %s
            """,
            (limit,),
        )
        st.dataframe(companies, use_container_width=True, hide_index=True)

        st.subheader("Event Company Links")
        links = load_dataframe(
            conn,
            """
            SELECT l.id,
                   e.event_name,
                   c.ts_code,
                   c.company_name,
                   l.link_type,
                   l.final_link_score,
                   l.text_similarity_score,
                   l.industry_match_score,
                   l.relation_path
            FROM event_company_links l
            JOIN structured_events e ON e.id = l.structured_event_id
            JOIN companies c ON c.id = l.company_id
            ORDER BY l.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        st.dataframe(links, use_container_width=True, hide_index=True)

    conn.close()


if __name__ == "__main__":
    main()
