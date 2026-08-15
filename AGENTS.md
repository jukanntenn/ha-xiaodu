# Xiaodu 集成 — AI Agent 指南

本文档为在本仓库工作的 AI 编程 Agent（Claude Code、Codex 等）提供协作规范。

## 项目结构

- `custom_components/xiaodu/` — 集成源码
    - `api/` — 小度云 API 客户端（`xiaodu_client.py`、`xiaodu_types.py`、`exceptions.py`）
    - `bemfa/` — 巴法云（Bemfa）MQTT 同步模块（`mqtt_client.py`、`api_client.py`、`sync_manager.py`、`state_publisher.py`）
    - 平台文件：`light.py`、`switch.py`、`climate.py`、`cover.py`、`lock.py`、`button.py`
    - 其他：`coordinator.py`、`entity.py`、`config_flow.py`、`const.py`、`room_mapping.py`、`diagnostics.py`
- `tests/` — pytest 测试套件
    - `fixtures/` — 真实抓取的 API 响应（xiaodu/、bemfa/）
    - `test_e2e/` — 端到端用户级场景

## 开发命令

prek 是唯一质量门控真相源（本地 commit / pre-push 与 CI 共用同一套定义，见 `prek.toml`）；钩子按 format（会改文件）/ lint（只读秒级）/ check（慢速验证）三组编排：

```bash
uv sync                                # 安装全部开发依赖
prek install                           # 安装 git 钩子（每个 clone 一次；见下方注）
prek run --all-files                   # 全量门控（与 CI lint job 完全一致；push 前必须跑一次）
prek run --group format --files <f>    # 只跑格式化组（与 AI 编辑后钩子一致）
prek run --group lint --all-files      # 只跑 lint 组（与 AI 停止前钩子一致）
prek run --group check --all-files     # 只跑测试（与 CI tests job / pre-push 钩子一致）
uv run pytest tests/test_light.py      # 运行单个测试文件
uv run basedpyright --writebaseline    # baseline 漂移时重生成基线（与代码改动同笔提交）
uv run ty check custom_components      # 类型检查（辅助二次校验，advisory）
python3 scripts/hassfest.py            # hassfest 结构校验（manifest/strings/translations；复用官方镜像，与 CI validate.yml 同源；prek 已内嵌）
prek update                            # 升级钩子版本（遵循 cooldown_days）
```

- ruff 版本唯一 pin 在 `pyproject.toml`（dev 依赖），prek 钩子经 `uv run ruff` 调用，无双 pin 漂移。
- `prek install` 需显式 `--hook-type pre-commit --hook-type pre-push --hook-type commit-msg`（prek 0.4.11 的 `default_install_hook_types` 对 TOML 配置不生效，裸 install 只装 pre-commit）。push 时 pre-push 钩子自动跑测试（check 组）；跳过单个钩子用 `SKIP=<id>`，全部跳过 `git push --no-verify`（慎用，CI 仍会拦截）。
- 工具类/辅助类脚本放在 `scripts/`，默认用 Python（跨平台），均已带 shebang 且可执行。

## 代码规范

- 常量必须集中放在 `const.py`（根）与 `bemfa/const.py`；禁止用字符串字面量作为配置键或设备类型码。
- 文件名必须用 snake_case；禁止 PascalCase 文件名。
- 类名必须用 PascalCase，并带 `Xiaodu` 或 `Bemfa` 前缀（如 `XiaoduLight`、`BemfaMQTTClient`）。
- 常量名必须用 UPPER_SNAKE_CASE。
- 模块依赖必须单向：platform → entity → coordinator → api/bemfa。禁止反向依赖。
- 完成改动前必须运行 `uv run ruff check` 与 `uv run basedpyright`。
- 避免引入新的 `Any`——`basedpyright` 以 `all` 模式运行；存量 `Any` 冻结在 `.basedpyright/baseline.json`，新增的会被拦截。
- 需要更新 `.basedpyright/baseline.json` 时，本地运行 `uv run basedpyright --writebaseline`；绝不让 CI 或钩子自动写入。
- 优先使用具体的 HA 类型（`HomeAssistant`、`ConfigEntry`、`XiaoduCoordinator`），而非 `Any`。
- `strings.json` / `translations/*.json` 的 `config.create_entry.*` 取值**必须是字符串**，禁止写成含 `description` 子键的 dict（那是 `step.*` 层级的结构）。`create_entry` 的文案通过 `description_placeholders` 注入占位符；`async_create_entry` 不传 `description` 时，HA 前端自动 fallback 到 `create_entry.default`。改动翻译后必须跑 hassfest（prek 已内嵌）。

## 测试规范

- 必须使用 `aioclient_mock_fixture` 范式（见 `tests/conftest.py`），让真实的 `XiaoduAPI` 跑在 mock 的 HTTP 之上。禁止 patch API 客户端类本身。
- 当多个控制命令共用一个 URL 时，必须用基于请求体的 `side_effect` 处理函数来区分。
- 避免单独的 `test_api.py`；API 客户端由平台测试和 e2e 场景覆盖（对齐 HA core 的 `flo` 范式）。
- 巴法云 MQTT（`BemfaMQTTClient.publish`）可被 patch；巴法云 HTTP 端点走 `aioclient_mock`。
- e2e 场景放在 `tests/test_e2e/`，覆盖六个用户级流程。

## 提交与 Pull Request

- 必须使用 Conventional Commits：`feat:`、`fix:`、`docs:`、`refactor:`、`test:`、`ci:`、`chore:`（另放行标准补充 `build`/`style`/`perf`/`revert`）。commit-msg 钩子（`scripts/check_commit_msg.py`）强制校验首行格式；git 自动生成的 Merge/Revert 提交放行。
- Changelog 手写维护：改动在 `## [Unreleased]` 下累积用户级中文描述（不含技术细节）。发布时打 `vX.Y.Z` tag，Release workflow 会自动创建 GitHub Release（正文取自 CHANGELOG，rc/beta 等预发布版本自动标记为 prerelease）并附带 `xiaodu.zip` 资产。

## AI Agent 钩子

四套 AI 工具钩子（`.claude` / `.codex` / `.zcode` / `.opencode`）都是 **prek 的薄封装**，不含任何门控逻辑，永不与 prek/CI 漂移：

| 平台 | 配置位置 | 说明 |
|---|---|---|
| Claude Code | `.claude/settings.json` | PostToolUse（`Edit\|Write`）+ Stop |
| Codex | `.codex/hooks.json` | PostToolUse（`apply_patch`，从补丁文本解析路径）+ Stop（需在用户级 `~/.codex/config.toml` 的 `[projects]` 标记 `trusted` 并在 `/hooks` 里 review hooks） |
| opencode | `.opencode/plugin/hooks.ts` | PostToolUse 静默格式化 + `session.idle` 门控；opencode 的 event hook 为旁路型，无法返回 `{"decision":"block"}`，改用 `client.session.prompt()` 注入合成消息逼 agent 继续（每轮至多一次，等价于其他平台的 Stop） |
| ZCode | 用户级 `~/.zcode/cli/config.json` + `.zcode/hooks/` 脚本 | 本机 ZCode runtime（v2.1.0）会无条件剥离项目级 `.zcode/config.json` 的 hooks（安全策略），故脚本放项目内、注册在用户级配置，详见 `.zcode/READM.md` |
| Trae | 无（复用 `.claude/settings.json`） | Trae 原生读取 Claude Code Hook 配置 |

- 编辑后（PostToolUse）：`prek run --group format --files <被编辑文件>`——ruff autofix/format + 行尾/文件尾卫生，静默永不阻断（prek 退出码 0/1 均容忍）。
- 停止前（Stop / session.idle）：`prek run --group lint --all-files`——ruff check、codespell、basedpyright lock、import-linter、deptry、uv lock、版本一致性、hassfest 等只读闸门。失败时输出 `{"decision": "block", "reason": ...}`——Claude Code / Codex / ZCode / Trae 四方原生一致的协议。**禁止输出 `continue: false`**（Codex 与 Trae 中其语义为"停止"且优先级更高，会反转意图）。
- `basedpyright` 在 lint 组以 `--baselinemode=lock` 运行——与 CI 同行为，错误数任意方向变化（上升或下降）都非零退出，绝不写入基线。`stop_hook_active` / `stopHookActive` 守卫防循环（Claude Code/Codex 与 ZCode 的 Stop 输入字段名不同）。
- baseline 漂移的根治门控是 prek 的 `basedpyright-lock` 本地钩子（见 `prek.toml`），它在 commit 前 + CI 的 `prek run --all-files` 双侧以 lock 模式运行，强制 baseline 更新与代码改动同笔提交。停止钩子是编辑期的早期拦截；commit 期的最终拦截靠 prek。
- 配置格式均与官方源码/文档对齐：openai/codex、anomalyco/opencode、claude-code-docs、TRAE 官方文档、zcode-hooks-poc。
- **hook 脚本必须带 shebang（`#!/usr/bin/env python3`）**：CI 的 ruff `EXE002`（可执行文件缺 shebang）会拦截；本地 WSL 下该规则被 ruff 显式豁免，存在"本地绿 CI 红"盲区，以 CI 为准。

## Home Assistant 集成备注

- `integration_type: hub`、`iot_class: cloud_polling`（见 manifest.json）。
- 状态存在 `config_entry.runtime_data`；配置放在 entry options。禁止创建项目自有的数据库——持久化由 HA 管理。
- 质量等级目标：silver（见 `custom_components/xiaodu/quality_scale.yaml`）。
- Python `>=3.13`，Home Assistant `>=2026.1.0`。

## CLAUDE.md 同步

`CLAUDE.md` 与本文件（`AGENTS.md`）作为独立副本维护，内容保持完全一致。`agents-claude-sync` prek 钩子会拒绝任何两者内容不一致的提交。
