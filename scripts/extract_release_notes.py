"""从 CHANGELOG.md 提取指定版本（Keep a Changelog 段落）作为 GitHub Release Notes。

用法：extract_release_notes.py <version> [changelog 路径]

- <version> 匹配 `## [<version>]` 标题（支持 `## [1.2.3]` 与 `## [1.2.3] - 2026-01-01` 两种形态）
- 输出该标题到下一个二级标题之间的全部内容到 stdout
- 未找到时打印错误到 stderr 并返回非零退出码
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VERSION_HEADING = re.compile(r"^##\s+\[([^\]]+)\]")
NEXT_SECTION = re.compile(r"^##\s")


def extract_section(version: str, changelog: Path) -> str | None:
    """返回版本对应段落正文；未找到时返回 None。"""
    lines = changelog.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        match = VERSION_HEADING.match(line)
        if not match or match.group(1).strip() != version:
            continue
        body: list[str] = []
        for next_line in lines[index + 1 :]:
            if NEXT_SECTION.match(next_line):
                break
            body.append(next_line)
        return "\n".join(body).strip() + "\n"
    return None


def main() -> int:
    """解析参数并输出提取结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="要提取的版本号（如 0.1.0rc1）")
    parser.add_argument(
        "changelog",
        nargs="?",
        default="CHANGELOG.md",
        help="changelog 文件路径（默认 CHANGELOG.md）",
    )
    args = parser.parse_args()

    changelog = Path(args.changelog)
    section = extract_section(args.version, changelog)
    if section is None:
        print(
            f"CHANGELOG.md 中未找到版本 [{args.version}] 的条目",
            file=sys.stderr,
        )
        return 1
    sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
