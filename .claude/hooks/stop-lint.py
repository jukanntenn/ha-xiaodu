"""Stop hook: lint before the agent finishes.

Runs `ruff check` and `basedpyright` (--baselinemode=discard).
On any failure, returns exit 0 with JSON {decision: block, reason: ...} so the
agent is told to keep working. On success, exits 0 with no output.

The `stop_hook_active` field guards against infinite block loops: if the agent
is already continuing from a prior block, this hook lets it stop.
"""

from __future__ import annotations

import json
import subprocess
import sys


def emit_block(reason: str) -> None:
    """Print a JSON block decision and exit 0 (no error code)."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    # Guard against infinite loop: if already re-prompted by a Stop hook, allow stop.
    if data.get("stop_hook_active"):
        return

    cwd = data.get("cwd") or None
    errors: list[str] = []

    # 1. ruff check (fast)
    proc = subprocess.run(
        ["uv", "run", "ruff", "check", "custom_components", "tests"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append("ruff check failed:\n" + (proc.stdout + proc.stderr).strip())

    # 2. basedpyright (discard mode: read baseline, never write it)
    proc = subprocess.run(
        ["uv", "run", "basedpyright", "--baselinemode=discard"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append("basedpyright failed:\n" + (proc.stdout + proc.stderr).strip())

    if errors:
        emit_block(
            "Lint failed — fix all errors below before finishing the session:\n\n"
            + "\n\n".join(errors)
        )
    # else: exit 0 with no output → agent may stop


if __name__ == "__main__":
    main()
