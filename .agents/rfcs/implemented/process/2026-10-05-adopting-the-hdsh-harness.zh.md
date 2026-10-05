# RFC: 采纳 hdsh harness

Status: implemented

[English](2026-10-05-adopting-the-hdsh-harness.md) | 中文

## 问题

在此变更之前，jukanntenn/ha-xiaodu 不携带任何 harness 机制：没有 prek 治理门禁、没有议题策略与生命周期自动化、没有双语文档配对，也没有 RFC（决策记录）、skill 与文档标准的脚手架。仓库约定活在评审者记忆里而非机器执行的检查中，每个接入问题都要从 harness 仓库自己的文档里找答案。

## 决策

本仓库经 `hdsh adopt apply` 采纳 ref 为 `main` 的 hdsh harness：钉在该 ref 的 prek 门禁集、以 composite action 承载的议题策略与生命周期 workflow、带合并驱动的双语文档配对语料、RFC 机制、各工作流 skill 与文档标准。议题管理对接由 `.github/issue-management/config.json` 描述的 `ha-xiaodu` 项目；已安装文件清单与摘要记录在 `.hdsh/adopt.manifest.json`，升级以更新的 ref 重跑 `hdsh adopt apply`。

## 备选方案

**维持无门禁。** 零安装成本，但约定始终没有强制力，漂移只能靠评审发现。

**手工复制 harness 文件。** 一次性复制可行，但 harness 每次改进后，升级都退化为逐文件手工对 diff——这正是 `hdsh adopt` 与其 manifest 要消除的失败模式。

## 后果

- 本仓库采纳 harness 的目录树约定：所有 README、`docs/**`、`.agents/rfcs/**` 进入双语配对语料。
- 生成文件归上游所有；`hdsh adopt verify` 报告漂移与剩余的 `TODO(adopt)` 占位符，对生成文件的改动应引回上游而非分叉。
- git 外状态——标签、Project 字段与状态、secrets 与 variables、分支保护——按 harness 的 ADOPT.md 清单另行配置。
