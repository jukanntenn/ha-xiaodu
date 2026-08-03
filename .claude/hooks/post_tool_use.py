#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import PurePath


def commands_for(path: PurePath) -> list[list[str]]:
    match path.suffix:
        case ".py" | ".pyi":
            return [
                ["uv", "run", "ruff", "check", "--fix", str(path)],
                ["uv", "run", "ruff", "format", str(path)],
            ]
        case _:
            return []


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(file_path, str):
        return

    for cmd in commands_for(PurePath(file_path)):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            sys.stderr.write(
                f"[post-tool-use] uv not found on PATH; skipped {cmd[3]}\n"
            )
            continue
        if result.returncode != 0:
            sys.stderr.write(
                f"[post-tool-use] {cmd[3]} reported issues for {file_path}:\n"
            )
            if result.stdout:
                sys.stderr.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
