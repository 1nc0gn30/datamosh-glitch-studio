"""Tests for exact-port loopback Origin and Host allowlist guards."""
import importlib
import unittest

MODS = ["datamosh_glitch_studio.ui_server"]


class TestOriginGuard(unittest.TestCase):
    def test_exact_port_local_origins_allowed(self):
        for name in MODS:
            m = importlib.import_module(name)
            for o in (
                None,
                "",
                "http://localhost:8081",
                "http://127.0.0.1:8081",
                "http://[::1]:8081",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ):
                self.assertTrue(m._is_local_origin(o, server_port=8081), (name, o))

    def test_foreign_and_non_allowlisted_ports_blocked(self):
        for name in MODS:
            m = importlib.import_module(name)
            for o in (
                "https://evil.example.invalid",
                "http://localhost.evil.example",
                "http://127.0.0.1:80810",
                "http://127.0.0.1:8080",
                "http://localhost:9000",
                "https://localhost:8081",
                "null",
                "file://",
                "http://192.168.1.5:8081",
            ):
                self.assertFalse(m._is_local_origin(o, server_port=8081), (name, o))

    def test_loopback_host_allowlist(self):
        for name in MODS:
            m = importlib.import_module(name)
            for h in ("127.0.0.1:8081", "localhost:8081", "[::1]:8081", "127.0.0.1", "localhost"):
                self.assertTrue(m._is_allowed_host(h, server_port=8081), (name, h))
            for h in ("", None, "evil.example.invalid", "127.0.0.1:9999", "evil.127.0.0.1:8081"):
                self.assertFalse(m._is_allowed_host(h, server_port=8081), (name, h))


if __name__ == "__main__":
    unittest.main()
