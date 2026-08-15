#!/usr/bin/env python3
"""版本一致性校验（prek lint 钩子）。

三处版本必须同步（比较时忽略 v 前缀等价）：

- ``custom_components/xiaodu/manifest.json`` 的 ``version``（含 v 前缀，与 release
  tag 完全一致——powercalc / ha-xiaomi-home 等 HA 社区集成惯例）
- ``pyproject.toml`` 的 ``[project].version``（PEP 440，无 v 前缀）
- ``CHANGELOG.md`` 最新的 ``## [X.Y.Z]`` 版本标题

发版用 ``scripts/bump_version.py`` 一次性同步三处，本钩子把漂移变成显式失败。
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "custom_components" / "xiaodu" / "manifest.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
VERSION_HEADING = re.compile(r"^##\s+\[([^\]]+)\]")


def read_versions() -> tuple[str, str, str | None]:
    """读取三处版本：manifest、pyproject、CHANGELOG 最新版本标题。"""
    manifest_version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    pyproject_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"][
        "version"
    ]
    changelog_version: str | None = None
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        match = VERSION_HEADING.match(line)
        if match and match[1] != "Unreleased":
            changelog_version = match[1]
            break
    return manifest_version, pyproject_version, changelog_version


def main() -> int:
    manifest_version, pyproject_version, changelog_version = read_versions()
    errors: list[str] = []

    for label, value in (
        ("manifest", manifest_version),
        ("pyproject", pyproject_version),
    ):
        try:
            Version(value.removeprefix("v"))
        except InvalidVersion:
            errors.append(f"{label} 版本 {value!r} 不是合法 PEP 440 版本")

    if manifest_version.removeprefix("v") != pyproject_version:
        errors.append(
            f"manifest.json version（{manifest_version}）与 pyproject.toml version"
            f"（{pyproject_version}）不一致（比较时忽略 v 前缀）"
        )
    if changelog_version is None:
        errors.append("CHANGELOG.md 中找不到任何 `## [X.Y.Z]` 版本标题")
    elif changelog_version.removeprefix("v") != pyproject_version:
        errors.append(
            f"CHANGELOG.md 最新版本标题 [{changelog_version}] 与 pyproject.toml "
            f"version（{pyproject_version}）不一致"
        )

    if errors:
        print("版本一致性校验失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print(
            "发版请运行：uv run python scripts/bump_version.py <X.Y.Z>", file=sys.stderr
        )
        return 1

    print(
        f"版本一致：manifest {manifest_version} == pyproject {pyproject_version} == CHANGELOG [{changelog_version}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
