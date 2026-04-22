from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.events.services import event_persistence_service


class EventPersistenceServiceTests(unittest.TestCase):
    @patch("modules.events.services.event_persistence_service.subprocess.run")
    @patch("modules.events.services.event_persistence_service.psycopg.connect")
    @patch("modules.events.services.event_persistence_service.dsn_for", return_value="postgresql://db")
    def test_insert_final_rows_runs_single_transaction(
        self,
        mock_dsn_for: MagicMock,
        mock_connect: MagicMock,
        mock_subprocess_run: MagicMock,
    ) -> None:
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        conn.cursor.return_value.__exit__.return_value = False
        mock_connect.return_value = conn

        event_persistence_service.insert_final_rows("stock_event_mining")

        mock_dsn_for.assert_called_once_with("stock_event_mining")
        mock_connect.assert_called_once_with("postgresql://db")
        self.assertEqual(cursor.execute.call_count, 3)
        cursor.execute.assert_has_calls(
            [
                call(event_persistence_service.FINAL_CANDIDATE_UPSERT_SQL),
                call(event_persistence_service.FINAL_STRUCTURED_UPSERT_SQL),
                call(event_persistence_service.FINAL_STRUCTURED_DELETE_SQL),
            ]
        )
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()
        conn.close.assert_called_once()
        mock_subprocess_run.assert_not_called()

    @patch("modules.events.services.event_persistence_service.upsert_raw_documents")
    @patch("modules.events.services.event_persistence_service.ensure_event_schema")
    @patch("modules.events.services.event_persistence_service.psycopg.connect")
    @patch("modules.events.services.event_persistence_service.dsn_for", return_value="postgresql://db")
    def test_load_stage_rows_wraps_both_stage_tables_in_one_transaction(
        self,
        mock_dsn_for: MagicMock,
        mock_connect: MagicMock,
        mock_ensure_event_schema: MagicMock,
        mock_upsert_raw_documents: MagicMock,
    ) -> None:
        copy_ctx = MagicMock()
        copy_ctx.__enter__.return_value = copy_ctx
        copy_ctx.__exit__.return_value = False

        cursor = MagicMock()
        cursor.copy.return_value = copy_ctx
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        conn.cursor.return_value.__exit__.return_value = False
        mock_connect.return_value = conn

        event_persistence_service.load_stage_rows(
            "stock_event_mining",
            raw_documents=[{"url": "https://doc-1"}],
            raw_candidates=[
                {
                    "url": "https://doc-1",
                    "dedup_key": "dedup",
                    "duplicate_group_size": "1",
                    "is_event": "true",
                    "filter_reason": "",
                    "evidence": "evidence",
                    "score_hint": "90",
                }
            ],
            structured_events=[
                {
                    "event_id": "evt-1",
                    "raw_text_ref": "https://doc-1",
                    "event_name": "事件",
                    "event_date": "2025-01-02",
                    "source": "巨潮资讯网/历史公告",
                    "event_subject_type": "上市公司",
                    "duration_type": "single_day",
                    "predictability_type": "unexpected",
                    "industry_type": "其他",
                    "sentiment": "neutral",
                    "heat_score": "50",
                    "intensity_score": "50",
                    "impact_scope": "company",
                    "event_summary": "summary",
                    "subject_entities": "[]",
                }
            ],
        )

        mock_ensure_event_schema.assert_called_once_with("stock_event_mining")
        mock_upsert_raw_documents.assert_called_once_with("stock_event_mining", [{"url": "https://doc-1"}])
        mock_dsn_for.assert_called_once_with("stock_event_mining")
        mock_connect.assert_called_once_with("postgresql://db")
        self.assertEqual(cursor.copy.call_count, 2)
        self.assertEqual(copy_ctx.write.call_count, 2)
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
