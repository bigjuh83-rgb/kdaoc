"""Shared MySQL client path helpers for Windows clients invoked from WSL."""

from __future__ import annotations

import os
import re
import tempfile


def windows_argument_path_for_wsl(path: str) -> str:
    match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", path)
    if not match:
        return path
    drive = match.group(1).upper()
    rest = match.group(2).replace("/", "\\")
    return f"{drive}:\\{rest}"


def writable_windows_client_defaults_dir(mysql_bin: str) -> str | None:
    mysql_dir = os.path.dirname(str(mysql_bin))
    if mysql_dir and os.path.isdir(mysql_dir) and os.access(mysql_dir, os.W_OK):
        return mysql_dir

    cwd = os.getcwd()
    if re.match(r"^/mnt/[a-zA-Z]/", cwd) and os.access(cwd, os.W_OK):
        return cwd

    temp_dir = tempfile.gettempdir()
    if re.match(r"^/mnt/[a-zA-Z]/", temp_dir) and os.access(temp_dir, os.W_OK):
        return temp_dir

    return None
