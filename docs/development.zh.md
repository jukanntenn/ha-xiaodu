# 开发指南

[English](development.md) | 中文

安装教程带新贡献者从前置条件走到可校验的检出；随后的贡献者参考覆盖日常工作流与仓库的工具集成。

## 安装教程

### 前置条件

Python >= 3.13 且 Home Assistant >= 2026.1.0；包管理器用 [uv](https://docs.astral.sh/uv/)；harness 工具链还需 git、[GitHub CLI](https://cli.github.com/) 与 [ripgrep](https://github.com/BurntSushi/ripgrep)。

### 首次安装

全新检出后依次执行 `uv sync`、`uv tool install "harness-deepseek-harness @ git+https://github.com/jukanntenn/harness-deepseek-harness@main"`、`prek install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg`、`hdsh worktree install`；`prek run --all-files` 全绿即安装完成。

## 贡献者参考

### 项目布局

一个名字在目录、接口与 id 前缀三处指同一概念；完整组件地图见 [architecture.md](architecture.zh.md)。

### 日常命令

`prek run --all-files`——CI 跑的全量门禁。`prek run --group check --group hdsh --all-files`——测试加 hdsh 文档门禁。`uv run pytest tests/test_light.py`——单个聚焦测试文件。`uv run basedpyright`——按冻结基线做类型检查。`hdsh pairing list`——还有哪些双语对缺对侧；审后 `hdsh pairing record <anchor>` 记录一对。文档门禁与双语配对工作流遵循[双语文档契约](i18n/README.zh.md)；门禁语料配置在 `.hdsh/docs.manifest.json` 与 `.hdsh/pairing.manifest.json`。

### TODO 标记

本仓库不在源码里留 TODO 标记；未决事项开 Issue，决策记录进 `.agents/rfcs/` 下的 RFC。
