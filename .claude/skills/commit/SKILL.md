---
name: commit
description: Use when 用户要求提交或暂存改动（commit/stage/save/submit），任务结束有脏文件需要提交，或多个文件需要按逻辑拆分为多个提交时。
---

按逻辑变更单元分组提交，不按文件。AI 起草方案、用户确认后执行；永不自动 push、永不 amend。

## 流程

1. `git status --porcelain` 查看改动；`git log --oneline -5` 看历史风格
2. 区分本次 AI 编辑的文件与未识别文件；未识别文件单独列出，不混入任何提交
3. 按逻辑变更单元分组，顺序：chore → feat → fix → refactor → docs → test → release 最后
4. 一次性展示提交计划；用户确认后逐批执行 `git add` + `git commit`；被拒绝则停止，不再重提
5. 提交前运行 `uv run pytest`（basedpyright 由 AI 停止钩子覆盖，无需手动运行）
6. 只有一个文件改动时跳过计划展示，直接提交

## 消息格式

`<type>: <desc>`：小写、祈使语气、无句号；中文文件用中文、英文文件用英文。
类型只用 `feat`/`fix`/`docs`/`refactor`/`test`/`ci`/`chore`（对应 Release Drafter 分区），本仓库不使用 scope。

## 边界情形

- 生成文件（锁文件、db）捆绑进产生它的提交，或单独 `chore` 提交
- CLAUDE.md 与 AGENTS.md 改动必须成对同步（`agents-claude-sync` 钩子会拒绝不一致提交）
- 未识别文件绝不静默包含；不 amend、不 push、不用占位消息（wip、update files）
