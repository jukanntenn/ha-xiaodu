"""检查 ruff 双 pin 一致性（pyproject.toml 与 prek.toml 版本必须相同）。

背景：ruff 版本同时锁定在 pyproject.toml（uv 依赖，dependabot 会自动升级）
与 prek.toml（ruff-pre-commit 钩子 rev，dependabot 无法触及）。
两者漂移会导致本地 `uv run ruff` 与 prek 钩子检查结果不一致（本地绿 CI 红）。
本脚本作为 prek 钩子把漂移变成显式失败。
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
PREK_CONFIG_FILE = REPO_ROOT / "prek.toml"
RUFF_PRE_COMMIT_REPO = "https://github.com/astral-sh/ruff-pre-commit"


def ruff_pyproject_version() -> str | None:
    """从 pyproject.toml 的 dev 依赖中提取 ruff 锁定版本。"""
    with PYPROJECT_FILE.open("rb") as f:
        data = tomllib.load(f)
    for group in data.get("dependency-groups", {}).values():
        for dep in group:
            if isinstance(dep, str):
                match = re.match(r"ruff==(\S+)", dep)
                if match:
                    return match.group(1)
    return None


def ruff_prek_rev() -> str | None:
    """从 prek.toml 的 ruff-pre-commit 仓库中提取 rev（去掉 v 前缀）。"""
    with PREK_CONFIG_FILE.open("rb") as f:
        data = tomllib.load(f)
    for repo in data.get("repos", []):
        if repo.get("repo") == RUFF_PRE_COMMIT_REPO:
            return repo.get("rev", "").removeprefix("v")
    return None


def main() -> int:
    """比较两处版本，不一致时返回非零退出码。"""
    pyproject_version = ruff_pyproject_version()
    prek_rev = ruff_prek_rev()
    if pyproject_version is None or prek_rev is None:
        print("无法定位 ruff 版本声明（pyproject.toml 或 prek.toml）", file=sys.stderr)
        return 1
    if pyproject_version != prek_rev:
        print(
            f"ruff 双 pin 不一致：pyproject.toml 为 ruff=={pyproject_version}，"
            f"prek.toml 为 rev=v{prek_rev}。请同步两处版本后重试。",
            file=sys.stderr,
        )
        return 1
    print(f"ruff 双 pin 一致：v{pyproject_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
