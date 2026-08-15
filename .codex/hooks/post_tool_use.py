#!/usr/bin/env python3
# Codex PostToolUse（apply_patch）：格式化委托给 prek（format 组，单一真相源）。
# Codex 载荷无 file_path 字段，从 apply_patch 命令文本解析被编辑路径，
# 一次 prek 调用处理全部路径。exit 0/1 均容忍，永不阻断。
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MOVE_TO_PREFIX = "*** Move to: "
PATCH_FILE_PREFIXES = (
    "*** Update File: ",
    "*** Add File: ",
)


def extract_edited_paths(command: str) -> list[str]:
    paths: list[str] = []
    pending_update: str | None = None
    for raw_line in command.splitlines():
        line = raw_line.strip()
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


def in_repo(raw_path: str) -> bool:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    try:
        path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    return path.is_file()


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return

    paths = [p for p in extract_edited_paths(command) if in_repo(p)]
    if not paths:
        return

    try:
        result = subprocess.run(
            ["prek", "run", "--group", "format", "--files", *paths],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("[codex-post-tool-use] prek 不在 PATH 上，跳过格式化\n")
        return

    if result.returncode not in (0, 1):
        sys.stderr.write(
            f"[codex-post-tool-use] prek format 退出码 {result.returncode}：\n"
        )
        if result.stdout:
            sys.stderr.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
