#!/usr/bin/env bash
# hassfest 本地校验 wrapper（prek hook 入口）。
#
# 复用官方 ghcr.io/home-assistant/hassfest 镜像，与 CI validate.yml 同源、同规则，
# 上游更新镜像即自动跟进，无规则漂移。镜像 entrypoint 会执行
# `find . -name manifest.json`，因此只能挂载 custom_components 子目录——若挂整个
# 仓库，会扫到 .venv 内 HA core 自带集成的 manifest（无 codeowners 字段）而误报
# KeyError。Docker 的 -v 不解析相对路径，故在此用绝对路径挂载。
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
    echo "[hassfest] 跳过：未检测到 docker。请安装 Docker 后重试，或依赖 CI 兜底。" >&2
    exit 0
fi

exec docker run --rm -v "$(pwd)/custom_components":/github/workspace \
    ghcr.io/home-assistant/hassfest
