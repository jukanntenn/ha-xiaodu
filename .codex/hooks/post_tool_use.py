#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import PurePath

MOVE_TO_PREFIX = "*** Move to: "
PATCH_FILE_PREFIXES = (
    "*** Update File: ",
    "*** Add File: ",
)


def extract_edited_paths(command: str) -> list[str]:
    paths: list[str] = []
    pending_update: str | None = None
    for raw in command.splitlines():
        line = raw.strip()
        if pending_update is not None and line.startswith(MOVE_TO_PREFIX):
            paths.append(line[len(MOVE_TO_PREFIX) :].strip())
            pending_update = None
            continue
        if pending_update is not None:
            paths.append(pending_update)
            pending_update = None
        if line.startswith(MOVE_TO_PREFIX):
            continue
        for prefix in PATCH_FILE_PREFIXES:
            if line.startswith(prefix):
                pending_update = line[len(prefix) :].strip()
                break
    if pending_update is not None:
        paths.append(pending_update)
    return paths


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

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return

    for raw_path in extract_edited_paths(command):
        for cmd in commands_for(PurePath(raw_path)):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
            except FileNotFoundError:
                sys.stderr.write(
                    f"[codex-post-tool-use] uv not found on PATH; skipped {cmd[3]}\n"
                )
                continue
            if result.returncode != 0:
                sys.stderr.write(
                    f"[codex-post-tool-use] {cmd[3]} reported issues for {raw_path}:\n"
                )
                if result.stdout:
                    sys.stderr.write(result.stdout)
                if result.stderr:
                    sys.stderr.write(result.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
