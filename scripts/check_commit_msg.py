#!/usr/bin/env python3
"""commit-msg 钩子：校验 Conventional Commits 格式。

prek 在 commit-msg stage 把提交信息文件路径作为 argv[1] 传入。只校验首行；
type 覆盖 AGENTS.md 约定列表及标准补充（build/style/perf/revert）。git 自动
生成的 Merge/Revert 提交放行。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"^(feat|fix|docs|refactor|test|ci|chore|build|style|perf|revert)"
    r"(\([^)]+\))?!?: .+"
)


def main() -> int:
    msg_file = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        msg = (
            Path(msg_file).read_text(encoding="utf-8") if msg_file else sys.stdin.read()
        )
    except OSError:
        msg = ""

    subject = msg.splitlines()[0] if msg.splitlines() else ""
    if subject.startswith(("Merge ", "Revert ")):
        return 0
    if not PATTERN.match(subject):
        print("ERROR: 提交信息必须符合 Conventional Commits 格式。")
        print("  期望：<type>(<scope>)?!?: <摘要>")
        print(
            "  type 取值：feat|fix|docs|refactor|test|ci|chore|build|style|perf|revert"
        )
        print(f"  实际：{subject}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
