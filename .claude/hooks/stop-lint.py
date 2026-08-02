#!/usr/bin/env python3
"""Stop hook: lint before the agent finishes.

Runs `ruff check`, `ruff format --check`, and `basedpyright` (--baselinemode=discard).
On any failure, returns exit 0 with JSON so the agent is told to keep working.
On success, exits 0 with no output.

Output protocol（源码实证，四平台原生一致）:
- Claude Code / Codex / ZCode / Trae 都读 `decision: block` + 非空 `reason`。
- 绝不能输出 `continue: false`：Codex 与 Trae 中它的语义是"停止"且优先级
  高于 `decision`，会把 block 意图反转。
- 防循环：Claude Code 与 Codex 的 Stop 输入都有 `stop_hook_active` 字段
  （Codex schema 实证），为 true 时直接放行；ZCode/Trae 用内置阻断次数
  上限（loop_limit，默认 5）兜底。
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

    # 2. ruff format --check (fast, mirrors the CI format gate)
    proc = subprocess.run(
        ["uv", "run", "ruff", "format", "--check", "custom_components", "tests"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append(
            "ruff format --check failed:\n" + (proc.stdout + proc.stderr).strip()
        )

    # 3. basedpyright (discard mode: read baseline, never write it)
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
    # 非 error 分支：退出 0 无输出，允许结束会话


if __name__ == "__main__":
    main()
