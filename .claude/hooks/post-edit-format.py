#!/usr/bin/env python3
"""PostToolUse hook: auto-format edited Python files with ruff.

Silent on failure — formatting is best-effort and never blocks an edit.
Reads the hook event JSON from stdin (Claude Code / Codex hook protocol).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return

    ext = Path(file_path).suffix
    if ext not in (".py", ".pyi"):
        return

    cwd = data.get("cwd") or None
    # ruff format + check --fix, swallow all errors (PostToolUse must not block)
    for cmd in (
        ["uv", "run", "ruff", "format", file_path],
        ["uv", "run", "ruff", "check", "--fix", file_path],
    ):
        try:
            subprocess.run(cmd, cwd=cwd, capture_output=True)
        except (FileNotFoundError, OSError):
            pass


if __name__ == "__main__":
    main()
