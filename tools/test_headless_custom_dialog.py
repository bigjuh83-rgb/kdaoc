#!/usr/bin/env python3
"""Unit checks for headless DAOC custom dialog packets."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_headless_module():
    module_path = Path(__file__).with_name("headless-daoc-client.py")
    spec = importlib.util.spec_from_file_location("headless_daoc_client_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HeadlessCustomDialogTests(unittest.TestCase):
    def test_accept_custom_dialog_uses_custom_dialog_type_and_accept_response(self) -> None:
        headless = load_headless_module()
        client = object.__new__(headless.HeadlessDaocClient)
        sent: list[tuple[int, bytes, int | None]] = []
        client.send_packet = lambda code, data=b"", session_id=None: sent.append((code, data, session_id))
        client.drain = lambda seconds: 0

        client.accept_custom_dialog()

        self.assertEqual(len(sent), 1)
        code, payload, session_id = sent[0]
        self.assertEqual(code, headless.CLIENT_PACKETS["dialog_response"])
        self.assertIsNone(session_id)
        self.assertEqual(payload[0:2], b"\x00\x00")
        self.assertEqual(payload[2:4], b"\x00\x01")
        self.assertEqual(payload[4:6], b"\x00\x00")
        self.assertEqual(payload[6], 0x06)
        self.assertEqual(payload[7], 0x01)


if __name__ == "__main__":
    unittest.main()
