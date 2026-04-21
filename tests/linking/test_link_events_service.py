from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.linking.services import link_events_service


class LinkEventsServiceTests(unittest.TestCase):
    @patch("modules.linking.services.link_events_service.psycopg.connect")
    @patch("modules.linking.services.link_events_service.write_guard")
    @patch("modules.linking.services.link_events_service.delete_stale_links", return_value=4)
    @patch("modules.linking.services.link_events_service.upsert_link")
    @patch("modules.linking.services.link_events_service.load_companies")
    @patch("modules.linking.services.link_events_service.build_cluster_events")
    @patch("modules.linking.services.link_events_service.load_structured_events")
    @patch("modules.linking.services.link_events_service.load_canonical_map_from_csv", return_value={})
    @patch("modules.linking.services.link_events_service.load_canonical_map_from_db", return_value={"evt-1": {"canonical_event_id": "canon-1"}})
    @patch("modules.linking.services.link_events_service.score_link")
    def test_run_linking_uses_db_canonical_map_fallback_and_upserts_links(
        self,
        mock_score_link: MagicMock,
        mock_load_canonical_db: MagicMock,
        _mock_load_canonical_csv: MagicMock,
        mock_load_structured_events: MagicMock,
        mock_build_cluster_events: MagicMock,
        mock_load_companies: MagicMock,
        mock_upsert_link: MagicMock,
        _mock_delete_stale_links: MagicMock,
        mock_write_guard: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        mock_write_guard.return_value.__enter__.return_value = None
        mock_write_guard.return_value.__exit__.return_value = False

        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value.__exit__.return_value = False
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_connect.return_value.__exit__.return_value = False

        mock_load_structured_events.return_value = [{"event_id": "evt-1"}]
        mock_build_cluster_events.return_value = [
            {
                "member_ids": [101, 102],
                "industry_type": "科技",
                "event_name": "测试事件",
            }
        ]
        mock_load_companies.return_value = [{"id": 7, "company_name": "测试公司"}]
        mock_score_link.return_value = (0.9, {"direct_symbol_score": 1, "direct_name_score": 0, "industry_match_score": 0})

        upserted, stale_deleted = link_events_service.run_linking(
            db="stock_event_mining",
            top_k=3,
            min_score=0.35,
            canonical_map_path="output/event_canonical_map.csv",
            progress_every=100,
            lock_timeout_sec=120,
        )

        mock_load_canonical_db.assert_called_once_with(mock_cur)
        self.assertEqual(mock_upsert_link.call_count, 2)
        self.assertEqual(upserted, 2)
        self.assertEqual(stale_deleted, 4)


if __name__ == "__main__":
    unittest.main()
