# 术语表

本表约定本仓库的中英术语统一译法，是双语文档配对翻译的双向真源。

**通用规则：**

- "中文"列为中文译文的正文默认用词。若该列为英文，则中文译文的正文中保留英文不翻译。
- 首次出现按"首次出现"列书写（带括号注释）；后续出现只写括号前的部分（可能为中文，也可能为英文），不出现括号内的注释。
- "不要译作"列为严格禁止的译法。
- 如果某术语已经作为另一个术语的组成部分被括注过（如 `agent harness（智能体框架）` 中已包含 `agent` 的括注），则该术语后续单独出现时无需再次括注。
- 工具名与人名（uv、prek、ruff、basedpyright、ty、pytest、Git、GitHub）保留英文原文，不入表。

## 缩写类（中英文文本中均使用缩写）

| English | 中文 | 首次出现           | 不要译作   | 备注                                                                                 |
| ------- | ---- | ------------------ | ---------- | ------------------------------------------------------------------------------------ |
| AI      | AI   | AI（人工智能）     |            |                                                                                      |
| API     | API  |                    |            |                                                                                      |
| CI      | CI   |                    |            |                                                                                      |
| e2e     | e2e  |                    |            |                                                                                      |
| CLI     | CLI  | CLI（命令行界面）  |            |                                                                                      |
| PR      | PR   | PR（Pull Request） |            |                                                                                      |
| RFC     | RFC  | RFC（决策记录）    | 征求意见稿 | 指本仓库 `.agents/rfcs/` 下的决策记录文件；作通用标准词（如 RFC 2119）使用时不加括注 |

## 英文类（中英文文本中均使用英文）

| English       | 中文          | 首次出现                    | 不要译作 | 备注                                       |
| ------------- | ------------- | --------------------------- | -------- | ------------------------------------------ |
| agent         | agent         | agent（智能体）             |          |                                            |
| agent harness | agent harness | agent harness（智能体框架） |          | 框架类组合词整体保留英文                   |
| blob hash     | blob hash     |                             |          | `git hash-object` 对文件内容算出的 SHA-1   |
| fail-closed   | fail-closed   |                             | 失败关闭 | 无法验证时拒绝继续并保留冲突，绝不带猜测合并 |
| harness       | harness       |                             |          | 指智能体框架本体时保留英文；组合词见上一行 |
| lint          | lint          |                             |          |                                            |
| locale        | locale        |                             |          | 语言区域语境保留英文；指代码值时保持代码体 |
| manifest      | manifest      | manifest（元数据清单）      |          |                                            |
| worktree      | worktree      |                             |          | git 工作区概念；指 `git worktree` 命令或目录本身时保留代码体 |

## 双语类（中英文文本各自使用中英文）

| English              | 中文            | 首次出现                         | 不要译作       | 备注                                                            |
| -------------------- | --------------- | -------------------------------- | -------------- | --------------------------------------------------------------- |
| actor                | 执行者          |                                  |                | 亦可译「操作者」；指动作的实际主体，用于补全句子主语            |
| base retargeting     | 基座重定        | 基座重定（base retargeting）     | 变基           | 指堆叠 PR 更改其 base 分支指向；与 rebase（变基）是两个动作     |
| bilingual pair       | 双语配对        | 双语配对（bilingual pair）       |                |                                                                 |
| consistency record   | 一致性记录      | 一致性记录（consistency record） |                | 与文档同目录的 `.i18n.yaml` 伴随文件                            |
| Cookbook             | 实操手册        |                                  |                | 文档标题用语                                                   |
| counterpart          | 对侧文件        |                                  | 对应物、配对物 | 双语配对语境；泛指「另一侧」时可写「另一侧」                    |
| coverage gate        | 覆盖率门禁      |                                  |                | pytest 分支覆盖率须达 100% 的合入门禁                           |
| fail-loud            | 显性失败        |                                  | 静默跳过       | 配置或状态错误必须立即报错，不得静默吞掉                        |
| fenced code block    | 围栏代码块      |                                  |                | 沿用 MDN 中文翻译                                              |
| gate                 | 门禁            |                                  | 关卡           |                                                                 |
| info string          | 信息字符串      |                                  |                | 指代码围栏 ``` 之后的语言标注；沿用 CommonMark 中文翻译         |
| Issue/PR policy      | 议题策略        | 议题策略（Issue/PR policy）      |                | Issue 与 PR 的模板、标签、类型与生命周期校验引擎                |
| language switcher    | 语言切换行      |                                  |                | 双语配对文件 H1 之后的互链行                                    |
| lifecycle            | 生命周期        |                                  |                |                                                                 |
| merge driver         | 合并驱动        | 合并驱动（merge driver）         |                | Git 按文件属性启用的自定义合并程序                              |
| pairing record       | 配对一致性记录  |                                  |                | 「一致性记录」的全称语境用词                                    |
| prek hook            | prek 钩子       |                                  |                |                                                                 |
| RFC 2119 keywords    | RFC 2119 关键词 |                                  |                | MUST／SHOULD／MAY；中文行文作「必须／应当／可以」并首现括注英文 |
| snapshot ref         | 快照引用        | 快照引用（snapshot ref）         |                | `refs/hdsh/pairing/snapshots/` 下的内容寻址 ref     |
| source of truth      | 真源            |                                  | 事实来源、唯一来源 |                                                             |
| stacked PR           | 堆叠 PR         | 堆叠 PR（stacked PR）            |                | 以另一 PR 为 base 的 PR；`stack` 作名词同译「堆叠」             |
| structural signature | 结构签名        |                                  |                | 门禁比对两侧文件时提取的有序结构序列（标题、代码块、列表等）    |
| terminal status      | 终态            |                                  | 最终状态       | 进程退出状态或生命周期的最终状态                                |
| typecheck            | 类型检查        |                                  |                |                                                                 |

## 待定术语

翻译时遇到表内未收录、又无通行译法依据的术语：正文保留英文，并在 PR 描述中按「术语、建议译法、出处」登记；评审定稿后移入上表，并在同一变更中同步更新相关译文。

- （暂无）
