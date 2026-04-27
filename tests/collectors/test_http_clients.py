from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.domain.common import get_http_session


class CollectorHttpClientTests(unittest.TestCase):
    def test_shared_http_session_ignores_environment_proxies(self) -> None:
        session = get_http_session()

        self.assertFalse(session.trust_env)

    def test_collector_aiohttp_sessions_opt_out_of_environment_proxies(self) -> None:
        collector_root = SRC / "modules" / "collectors"
        offenders: list[str] = []
        for path in collector_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "aiohttp.ClientSession()" in text:
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
