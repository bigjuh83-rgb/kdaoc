#!/usr/bin/env python3
"""Unit checks for behavior dummy local API host selection."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def load_module():
    module_path = Path(__file__).with_name("behavior-dummy-client.py")
    spec = importlib.util.spec_from_file_location("behavior_dummy_client_api_host_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


behavior = load_module()


class BehaviorDummyApiHostTests(unittest.TestCase):
    def test_posix_client_uses_server_host_for_local_api(self) -> None:
        args = SimpleNamespace(host="192.168.0.42", api_host="")

        with mock.patch.object(behavior.os, "name", "posix"):
            self.assertEqual(behavior.api_host_for_local_client(args), "192.168.0.42")

    def test_windows_client_keeps_loopback_for_non_loopback_server_host(self) -> None:
        args = SimpleNamespace(host="192.168.0.42", api_host="")

        with mock.patch.object(behavior.os, "name", "nt"):
            self.assertEqual(behavior.api_host_for_local_client(args), "127.0.0.1")

    def test_explicit_api_host_wins(self) -> None:
        args = SimpleNamespace(host="192.168.0.42", api_host="10.0.0.5")

        with mock.patch.object(behavior.os, "name", "nt"):
            self.assertEqual(behavior.api_host_for_local_client(args), "10.0.0.5")


if __name__ == "__main__":
    unittest.main()
