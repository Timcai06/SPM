from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.runtime.services.network_env_service import direct_network_only, without_process_proxies


class NetworkEnvServiceTests(unittest.TestCase):
    def test_without_process_proxies_temporarily_clears_proxy_keys(self) -> None:
        env = {
            "HTTP_PROXY": "http://proxy.internal:7890",
            "HTTPS_PROXY": "http://proxy.internal:7890",
            "ALL_PROXY": "socks5://proxy.internal:7891",
            "NO_PROXY": "localhost,127.0.0.1",
        }
        with patch.dict(os.environ, env, clear=True):
            with without_process_proxies():
                self.assertNotIn("HTTP_PROXY", os.environ)
                self.assertNotIn("HTTPS_PROXY", os.environ)
                self.assertNotIn("ALL_PROXY", os.environ)
                self.assertEqual(os.environ.get("NO_PROXY"), "localhost,127.0.0.1")

            self.assertEqual(os.environ.get("HTTP_PROXY"), env["HTTP_PROXY"])
            self.assertEqual(os.environ.get("HTTPS_PROXY"), env["HTTPS_PROXY"])
            self.assertEqual(os.environ.get("ALL_PROXY"), env["ALL_PROXY"])
            self.assertEqual(os.environ.get("NO_PROXY"), env["NO_PROXY"])

    @patch("modules.runtime.services.network_env_service._default_route_interface", return_value="en0")
    @patch("modules.runtime.services.network_env_service._read_scutil_proxy_flags", return_value={})
    def test_direct_network_only_allows_direct_route(self, _mock_proxy: object, _mock_route: object) -> None:
        env = {
            "HTTP_PROXY": "http://proxy.internal:7890",
            "HTTPS_PROXY": "http://proxy.internal:7890",
        }
        with patch.dict(os.environ, env, clear=True):
            with direct_network_only():
                self.assertNotIn("HTTP_PROXY", os.environ)
                self.assertNotIn("HTTPS_PROXY", os.environ)

    @patch(
        "modules.runtime.services.network_env_service._read_scutil_proxy_flags",
        return_value={"HTTPEnable": "1", "HTTPSEnable": "0", "SOCKSEnable": "0"},
    )
    def test_direct_network_only_rejects_system_proxy(self, _mock_proxy: object) -> None:
        with self.assertRaises(SystemExit) as ctx:
            with direct_network_only():
                pass
        self.assertIn("macOS proxy settings are active", str(ctx.exception))

    @patch("modules.runtime.services.network_env_service._default_route_interface", return_value="utun5")
    @patch("modules.runtime.services.network_env_service._read_scutil_proxy_flags", return_value={})
    def test_direct_network_only_rejects_tunnel_default_route(self, _mock_proxy: object, _mock_route: object) -> None:
        with self.assertRaises(SystemExit) as ctx:
            with direct_network_only():
                pass
        self.assertIn("default route is using tunnel interface", str(ctx.exception))
