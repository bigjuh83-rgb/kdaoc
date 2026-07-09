#!/usr/bin/env python3
"""Compatibility entrypoint for the importable behavior dummy client."""

from behavior_dummy_client import *  # noqa: F401,F403
from behavior_dummy_client import main


if __name__ == "__main__":
    raise SystemExit(main())
