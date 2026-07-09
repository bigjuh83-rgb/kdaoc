#!/usr/bin/env python3
"""Compatibility entrypoint for the importable dummy growth suite."""

from dummy_growth_suite import *  # noqa: F401,F403
from dummy_growth_suite import main


if __name__ == "__main__":
    raise SystemExit(main())
