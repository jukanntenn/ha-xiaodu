#!/usr/bin/env python3
# Claude Code PostToolUse（Edit|Write）：格式化委托给 prek（format 组，单一真相源），
# 本脚本不含任何格式化逻辑。exit 0 = 干净，1 = 有文件被修改（格式化钩子的预期
# 行为），仅更高退出码视为真实错误上屏，永不阻断。
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(file_path, str):
        return
    path = Path(file_path)
    if not path.is_absolute():
        path = ROOT / path
    try:
        path.resolve().relative_to(ROOT)
    except ValueError:
        return
    if not path.is_file():
        return

    try:
        result = subprocess.run(
            ["prek", "run", "--group", "format", "--files", file_path],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("[post-tool-use] prek 不在 PATH 上，跳过格式化\n")
        return

    if result.returncode not in (0, 1):
        sys.stderr.write(f"[post-tool-use] prek format 退出码 {result.returncode}：\n")
        if result.stdout:
            sys.stderr.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
