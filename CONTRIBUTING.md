# 贡献指南

感谢你愿意为 Xiaodu for Home Assistant 投入时间！代码、测试、文档、翻译、新设备类型支持等形式的贡献都受欢迎。参与本项目（issue、PR、Discussions 等）即表示你同意遵守[行为准则](.github/CODE_OF_CONDUCT.md)。

## 贡献方式

- **报告 bug**：使用 [bug 表单](https://github.com/jukanntenn/ha-xiaodu/issues/new?template=bug.yml)，按字段引导填写
- **功能建议与使用疑问**：先到 [Discussions](https://github.com/jukanntenn/ha-xiaodu/discussions) 对应分类讨论（想法 / 问答），形成共识后再转化为具体的功能 issue
- **代码 / 文档 / 翻译**：从 [good first issue](https://github.com/jukanntenn/ha-xiaodu/labels/good%20first%20issue) 标签的 issue 入手

## 基本规则

- **任何变更先开 issue——包括错字修正。** 先开一个简短的 issue，再提关联它的 PR；未关联 issue 的 PR 可能被直接关闭。这能保持工作可见、避免重复劳动。
- **非平凡变更先达成共识。** 涉及新平台接入、巴法云协议语义、配置 schema、依赖变更、lint / 门禁配置的改动，请先在 issue 或 Discussions 中讨论并获得维护者认可后再动手。

## 开发环境

- Python ≥ 3.13，[uv](https://docs.astral.sh/uv/) 管理依赖，Docker（本地跑 hassfest 校验用）

```bash
uv sync                                                                     # 安装全部开发依赖
prek install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
```

> 注意：prek 0.4.11 下裸 `prek install` 只装 pre-commit 钩子，必须显式带上三种 `--hook-type`。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `uv run pytest tests/test_light.py` | 运行单个测试文件 |
| `prek run --all-files` | 全量质量门禁（本地 / pre-push / CI 同一套，没有第二标准） |
| `prek run --group check --all-files` | 只跑测试组 |
| `python3 scripts/hassfest.py` | 集成结构校验（manifest / strings / translations） |

## 代码规范

- 常量集中放在 `const.py` 与 `bemfa/const.py`；禁止用字符串字面量作为配置键或设备类型码
- 类名 PascalCase 并带 `Xiaodu` / `Bemfa` 前缀；文件名 snake_case；常量名 UPPER_SNAKE_CASE
- 模块依赖必须单向：platform → entity → coordinator → api / bemfa，禁止反向依赖
- 避免引入新的 `Any`：basedpyright 以 `all` 模式运行，存量 `Any` 冻结在 `.basedpyright/baseline.json`，新增的会被拦截；优先使用具体 HA 类型
- 中英文混排时在中文与英文之间加空格；品牌命名统一——首现写「小度（Xiaodu）」其后用「小度」，巴法云与 Bemfa 并注，Home Assistant 永不翻译

## 测试规范

- 必须使用 `aioclient_mock_fixture` 范式（见 `tests/conftest.py`），让真实的 `XiaoduAPI` 跑在 mock 的 HTTP 之上；**禁止 patch API 客户端类本身**
- 当多个控制命令共用一个 URL 时，用基于请求体的 `side_effect` 处理函数区分
- 巴法云 MQTT（`BemfaMQTTClient.publish`）可被 patch；巴法云 HTTP 端点走 `aioclient_mock`
- 用户级端到端场景放在 `tests/test_e2e/`

## 翻译贡献

`strings.json` 是翻译源文件，`translations/en.json` 与 `translations/zh-Hans.json` 是镜像。注意 `config.create_entry.*` 的取值**必须是字符串**，不能写成含 `description` 子键的 dict（那是 `step.*` 层级的结构）。改动翻译后必须运行 `python3 scripts/hassfest.py` 校验。

## 提交与 Pull Request

- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-cn/)（`feat:`、`fix:`、`docs:`、`test:`、`refactor:`、`chore:` 等），commit-msg 钩子强制校验；不要用 `--no-verify` 绕过钩子
- CHANGELOG 在 `## [Unreleased]` 下累积**用户级**的中文描述（不讲技术细节）
- PR 前本地运行 `prek run --all-files` 必须通过——CI 跑的就是同一套门禁
- PR 按模板填写核对清单，用 `Fixes #NN` 关联 issue；欢迎先提 draft PR 获取早期反馈

## 接受范围

- **欢迎直接贡献**：bug 修复、新设备类型支持、测试与覆盖率、文档、翻译
- **先讨论再动手**：新平台接入、巴法云协议变更、依赖变更、配置 schema 调整、lint / 门禁配置修改

## AI 辅助贡献

本仓库欢迎 AI 辅助开发，并为 agent 配有完整的指令体系（`AGENTS.md` 与 `.agents/skills/`）。驱动 agent 工作时，请让它先读 `AGENTS.md`。无论代码是否由 AI 生成，提交者都需要完全理解并能解释所提交的内容。

## 求助

开发相关的问题请到 [Discussions](https://github.com/jukanntenn/ha-xiaodu/discussions) 提问；支持渠道的完整分流见 [SUPPORT.md](.github/SUPPORT.md)。

## 许可

提交 PR 即表示你同意你的贡献以 [MIT License](LICENSE) 与仓库一同发布。本项目不要求签署 CLA。
