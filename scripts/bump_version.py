#!/usr/bin/env python3
"""发版版本同步脚本：一次性更新三处版本并保持一致。

用法：``uv run python scripts/bump_version.py <X.Y.Z | vX.Y.Z> [YYYY-MM-DD]``

- ``custom_components/xiaodu/manifest.json`` → ``v<X.Y.Z>``（完整 tag，HA 社区惯例）
- ``pyproject.toml`` ``[project].version``   → ``<X.Y.Z>``（PEP 440）
- ``CHANGELOG.md``：``## [Unreleased]`` → ``## [<X.Y.Z>] - <日期>``，顶部补一个空的
  Unreleased 段

提交后打 tag 触发发布：``git tag v<X.Y.Z> && git push origin main v<X.Y.Z>``，
Release workflow 自动创建 GitHub Release（含 xiaodu.zip；rc 预发布自动标记
prerelease）。
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from packaging.version import InvalidVersion, Version

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "custom_components" / "xiaodu" / "manifest.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# 注意用 [ \t]* 而非 \s* 收尾：\s 会连标题后的换行一起吃掉，导致替换后
# 新版本标题与下方内容之间丢失空行。
UNRELEASED_HEADING = re.compile(r"^##\s+\[Unreleased\][ \t]*$", re.MULTILINE)
MANIFEST_VERSION = re.compile(r'("version"\s*:\s*")[^"]+(")')
PYPROJECT_VERSION = re.compile(r'(^version\s*=\s*")[^"]+(")', re.MULTILINE)


def fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2

    try:
        version = str(Version(sys.argv[1].removeprefix("v")))
    except InvalidVersion:
        return fail(f"{sys.argv[1]!r} 不是合法 PEP 440 版本")
    date = (
        sys.argv[2]
        if len(sys.argv) == 3
        else dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    )

    manifest, n_manifest = MANIFEST_VERSION.subn(
        rf"\g<1>v{version}\g<2>", MANIFEST.read_text(encoding="utf-8"), count=1
    )
    if n_manifest != 1:
        return fail("manifest.json 中未找到 version 字段")
    pyproject, n_pyproject = PYPROJECT_VERSION.subn(
        rf"\g<1>{version}\g<2>", PYPROJECT.read_text(encoding="utf-8"), count=1
    )
    if n_pyproject != 1:
        return fail("pyproject.toml 中未找到 [project].version")
    changelog, n_changelog = UNRELEASED_HEADING.subn(
        f"## [Unreleased]\\n\\n## [{version}] - {date}",
        CHANGELOG.read_text(encoding="utf-8"),
        count=1,
    )
    if n_changelog != 1:
        return fail("CHANGELOG.md 中未找到 `## [Unreleased]` 段标题")

    MANIFEST.write_text(manifest, encoding="utf-8")
    PYPROJECT.write_text(pyproject, encoding="utf-8")
    CHANGELOG.write_text(changelog, encoding="utf-8")

    print(f"已同步版本 {version}（{date}）：")
    print(f"  - manifest.json version -> v{version}")
    print(f"  - pyproject.toml version -> {version}")
    print(f"  - CHANGELOG.md -> ## [{version}] - {date}（顶部已补空 Unreleased 段）")
    print()
    print(f"下一步：git add -A && git commit -m 'chore(release): v{version}'")
    print(f"        git tag v{version} && git push origin main v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
