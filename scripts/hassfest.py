#!/usr/bin/env python3
"""hassfest 本地校验 wrapper（prek hook 入口）。

复用官方 ghcr.io/home-assistant/hassfest 镜像，与 CI validate.yml 同源、同规则，
上游更新镜像即自动跟进，无规则漂移。镜像 entrypoint 会执行
`find . -name manifest.json`，因此只能挂载 custom_components 子目录——若挂整个
仓库，会扫到 .venv 内 HA core 自带集成的 manifest（无 codeowners 字段）而误报
KeyError。无 Docker 时温和跳过，依赖 CI 兜底。
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
            f"{REPO_ROOT / 'custom_components'}:/github/workspace",
            "ghcr.io/home-assistant/hassfest",
        ],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
