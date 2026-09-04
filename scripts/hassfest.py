#!/usr/bin/env python3
"""hassfest 本地校验 wrapper（prek hook 入口）。

复用官方 ghcr.io/home-assistant/hassfest 镜像，与 CI validate.yml 同源、同规则，
上游更新镜像即自动跟进，无规则漂移。与官方 action 保持一致：挂载整个仓库到
/github/workspace——镜像 entrypoint 只在 custom_components/<domain>/manifest.json
与根级 manifest.json 两处发现集成，不会扫到 .venv 内 HA core 自带集成
（2026-09 起的镜像；旧镜像全仓 `find . -name manifest.json`，故当时只能挂
custom_components 子目录）。无 Docker 时温和跳过，依赖 CI 兜底。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if shutil.which("docker") is None:
        print(
            "[hassfest] 跳过：未检测到 docker。请安装 Docker 后重试，或依赖 CI 兜底。",
            file=sys.stderr,
        )
        return 0

    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{REPO_ROOT}:/github/workspace",
            "ghcr.io/home-assistant/hassfest",
        ],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
