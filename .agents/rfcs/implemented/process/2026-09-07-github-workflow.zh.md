# RFC: GitHub 工作流：原生 stack、PR 标签与 Issue 生命周期自动化

Status: implemented

[English](2026-09-07-github-workflow.md) | 中文

## 问题

工作流的 GitHub 侧必须回答四个代码和评审者记忆都承载不了的问题。仅由基线分支表示的依赖 PR 链没有官方的 stack 身份：落地它意味着逐个合并 PR、保留中间分支、重定向每个子 PR，事后再重建链条是否幸存。Pull request 标签回答两个彼此独立的问题——这项工作做的是哪种变更、它实质影响哪些持久领域——混淆这两个维度，或同时保留同义的裸标签与带命名空间的标签，都会让查询变得含糊，而封闭的 area 清单会把新领域挤进不准确的类别；Issue 已经带有原生 Type 和独立的 source 分类，在其上复用 PR 标签只会重复元数据。Issue Project 状态记录的是谁拥有解决工作的下一步，但 GitHub 的聚合评审状态无法表达这种交接：作者修完代码再次请求评审后，更早的 `CHANGES_REQUESTED` 评审仍然有效，而单调投影无法把自动化拥有的 Issue 从 `In review` 退回 `In progress`。规划元数据也需要一个归属：组织级 Issue 字段需要与组织 Projects 分开的 GitHub App 权限，同时存放在两套系统里会让一条政策依赖两套独立管理的权限集。

## 决策

### 依赖 PR 以原生 GitHub stack 落地

同一仓库内两个及以上依赖 PR 组成的每条链在落地前都使用 GitHub 的官方 stack 对象。实时的 `PullRequest.stack` 与 `stackEntry.position` 字段是权威。作者唯一的未堆叠链用 `gh stack link` 按自底向上顺序自动关联；作者混杂或不可用时需要用户确认。缺少原生支持和跨 fork 的链硬停止。已属于互相冲突的 stack，或官方顺序与分支拓扑不一致时，在解散或重建任何 stack 之前都需要用户指示。

"落地 stack"通过 `gh stack merge <stack-number> --yes --merge` 合并完整的官方 stack。部分落地需要显式的边界 PR，并通过该 PR 合并底部前缀。工作流从不回退到逐个 `gh pr merge` 加手动重定向。直接的原生合并要么全部成功要么全部失败；合并队列可能把选定的 PR 分成不同批次处理，因此每个选定 PR 都必须独立到达 `MERGED` 状态，落地才算完成。任何重写推送之后，当前头、未解决的评审线程、批准、可合并性和检查都要重新审计，因为先前的提交 OID 和行内锚点可能已过时。[本地 Git 工作流](2026-09-07-local-git-workflow.zh.md)拥有刷新历史本身——merge-forward 检查点与租约保护的 rebase——[堆叠 PR 落地技能](../../../skills/merging-stacked-prs/SKILL.md)承载具体流程。

### 标签：恰一个 kind、每个实质 area

每个开放或已合并的 pull request 恰好携带一个规范的 `kind/*` 标签和至少一个实质受影响的 `area/*` 标签。从未合并即关闭的 pull request 保留历史分配，但不获得杜撰的分类。运维类标签可以共存而不必满足任一维度。

kind 集合封闭且互斥：

| Kind | 含义 |
|---|---|
| `kind/feature` | 新增或有意改变行为。 |
| `kind/bug-fix` | 纠正错误行为。 |
| `kind/doc` | 以文档为主要意图。 |
| `kind/testing` | 改变测试或测试基础设施而不改变产品行为。 |
| `kind/cleanup` | 保持行为不变，维护或简化实现或仓库流程。 |
| `kind/dependency` | 更新依赖且没有其他主要意图。 |

kind 记录主要意图：随附的测试、文档、清理或依赖变动不会覆盖 feature 或 bug fix；新增 kind 会改变这些规则，需要显式的分类法与政策变更。仓库政策拒绝不受支持的 `kind/*` 值。

area 命名持久的产品或工程主题，而非临时举措、归属关系或每个附带触及的路径。一个 pull request 改变多个不同行为或 API 时携带多个 area，但绝不为同一变更同时挂上伞形标签和更窄的标签。GitHub 上实时的 `area/*` 名称与描述拥有当前清单，且该集合有意可扩展：当没有任何现有描述能诚实覆盖一个持久、可复用的领域时，agent 可以不经单独批准创建简洁的 `area/<lowercase-kebab-case>` 标签，但不得为单个 pull request、附带路径、临时项目、状态或个人/团队创建 area，并在应用后向请求者报告新标签及其理由。仅为回避一次合理的新增而复用不准确的 area 是不可接受的。

Issue 使用原生 Issue Type 而非 `kind/*`，其 `area/*` 标签保持可选。`source/*` 标签记录 Issue 如何被创建，不适用于 pull request。优先级、GitHub 默认标签和工作流触发器仍是独立的运维元数据。标签迁移在移除别名前先保留语义：添加规范替代、核实被标记对象、再移除过时分配；只有在没有任何 pull request 或 Issue 仍在使用时才删除标签，且从不成批替换无关标签。

### Issue Project 状态把评审事件当作命令

Issue 生命周期工作流（`.github/workflows/issue-lifecycle.yml`）把评审 webhook 当作命令，经由 `hdsh policy` 引擎 中的政策引擎分派，以 `hdsh policy lifecycle --config .github/issue-management/config.json` 调用，事件取自 `--event` 或 `GITHUB_EVENT_PATH`。`pull_request.review_requested`（包括重复请求）目标为 `In review`。`pull_request_review.submitted` 仅当 `review.state` 为 `changes_requested` 时目标为 `In progress`；submitted 事件仍然必要，因为评审者可以在没有先前评审请求事件的情况下请求修改。批准和评论型提交会运行其生命周期作业但不做任何事——它们永远到不了 Project 令牌步骤，因此不会铸造具有写权限的令牌——已撤销的评审不被订阅。

其余被订阅的普通 pull request 事件仍是只向前的实现信号：它们可以把 `Inbox`、`Backlog` 或 `Ready` 推进到 `In progress`，但永远不会把 `In review` 向后移动。评审请求命令可以把任何更早的活跃状态推进到 `In review`。请求修改命令可以把更早的活跃状态向前推进到 `In progress`，而只有当目标 Project 的最新状态事件是由配置的生命周期执行者写入时，才能把 `In review` 退回；最新执行者是人类或未知时保持当前状态。

状态投影只解析同一仓库内精确的 `Fixes`、`Closes` 或 `Resolves` 引用。它不改动终态、不添加没有 Project 状态的 Issue、不依赖 PR 元数据的有效性、不查询 `reviewDecision`、不重建评审轮次、不从 Issue 反查 pull request，也不运行定时对账器。生命周期工作流不订阅 `pull_request.ready_for_review`；政策工作流（`.github/workflows/issue-policy.yml`，`hdsh policy pr`）保留它，因为该工作流拥有人类 pull request 进入评审时的必需检查执行。

### 规划字段存放在 Project 中

`HDSH Issue Management` Project 以 Project 自定义字段的形式拥有 `Priority` 和 `Start Date`。政策从配置的 Project 解析这两个字段，拒绝基于 Issue 的字段或错误的数据类型，从 Project 条目读取 `Priority`，并通过 `updateProjectV2ItemFieldValue` 写入 `Start Date`。

政策工作流用仓库 `GITHUB_TOKEN` 做 REST 的 Issue 与 pull request 读取，用一个仅限仓库 Issues 和组织 Projects 读权限的 GitHub App 令牌做 ProjectV2 查询；生命周期的变更操作使用具有写权限的 App 令牌。个人账户部署以一枚只带 `project` scope 的 classic PAT（`HDSH_PROJECT_PAT`）取代 App 做 ProjectV2，REST 走 `github.token`；该形态由[个人账户支持 RFC](../feature/2026-09-08-user-account-issue-policy.zh.md)持有。生命周期工作流只在 `pull_request.opened` 时初始化 `Start Date`：它读取 pull request 的实时正文，保留每个解析为 Issue 的同仓库引用，把 `created_at` 转换为配置的 Project 时区下的日历日期，确保该 Issue 是 Project 条目，且仅当 Project 当前值为空时才写入日期。

### 评审回路

评审修复先落在引入缺陷的那个 PR 上，然后再传播到依赖层；[stack 评审 cookbook](../../../../docs/cookbook/responding-to-pr-review-on-a-stack.zh.md)拥有传播流程。[代码评审技能](../../../skills/reviewing/SKILL.md)引导评审者了解本仓库的标准和仅靠代码无法看出的检查项，[推送前检查技能](../../../skills/pushing/SKILL.md)拥有发布前的证据选择。技能承载流程；本记录承载它们所实现的决策。

## 验证

`tests/policy/` 钉住封闭的 kind 集合、恰一个 kind 与至少一个 area 规则、Issue 侧禁令、事件到命令的映射、请求修改命令之后的重复评审请求转换、请求修改回退、终态保护、人类覆盖保留、`Priority` 与 `Start Date` 的 Project 自定义字段要求、仓库读取与 Project 读取的凭据分离、配置时区的日期边界、仅 opened 分派、空值写入、既有值保留、缺失的 Project 条目，以及 `updateProjectV2ItemFieldValue` 变更。工作流文件的订阅事件、令牌与看板步骤上的步骤级门控、只读的 Project 令牌权限，以及独立的 `ready_for_review` 政策触发器，由对两个工作流文件的评审覆盖。落地流程核实原生支持、同仓库分支、实时作者、官方成员资格与顺序、合并范围和最终已合并状态。

## 备选方案

**把分支链作为唯一的 stack 表示。** 这保留了手动流程，却不给 GitHub 任何 stack 对象来展示顺序、在每一层执行主干规则或原子地合并一个区间。

**采用原生 stack 但禁止评审后使用其 rebase 命令。** 这保持了提交 OID 稳定，却在 stack 处于活跃评审时禁用了官方同步路径，并让独立 PR 处于不同政策之下。

**自动解散冲突的 stack。** 这会让本地分支推断覆盖共享的 GitHub 元数据，并可能干扰所请求链之外的 PR 或作者；已合并和已排队的条目并非总能移除。

**无前缀标签。** 裸名称减少视觉噪音，却无法辨认一个标签分类的是意图、领域、来源、优先级还是自动化，同时保留裸名与带命名空间的同义词又会让查询和政策执行含糊。

**一个不加区分的标签集合。** 标签的存在无法证明意图和语义范围都已被考虑。

**仓库政策中的固定 area 允许列表。** 持久的仓库领域会演化；`area/*` 命名空间保持机械可识别，而实时描述承载可扩展的清单。

**按包或路径派生的 area。** area 描述跨越包边界的语义影响，而变更路径包含附带的测试、文档和辅助文件。

**在 Issue 上使用 kind。** 原生 Issue Type 已经拥有该分类；以标签重复它会造成漂移。

**每个 pull request 恰好一个 area。** 连贯的变更可能实质影响多个独立的 API 或行为，丢弃次要 area 会隐藏受影响范围。

**从 `reviewDecision` 或重建的评审轮次派生状态。** 重复评审请求之后 GitHub 的聚合状态可能仍为 `CHANGES_REQUESTED`，而轮次归约器引入了超出两次显式交接的评审者与顺序语义。

**保留只向前的投影。** 单调推进保护了后续状态，却让 Issue 在作者实现所请求的修改期间停留在 `In review`。

**无条件应用每个评审命令。** 这是最小的事件处理器，却让自动化覆盖人类拥有的 Project 状态；因此目标 Project 的最新状态执行者守卫唯一的后退转换。

**让生命周期订阅 `ready_for_review` 或增加去抖队列。** Ready 状态不承载任何一种评审交接，而另一个队列会增加延迟和控制面状态，却不改变任何一个命令。

**保留组织级 Issue 字段用于规划。** 它们让一个值跨 Project 可见，但没有工作流需要该范围，而 GitHub App 需要单独的组织 Issue Fields 访问权限。

**双写 Issue 字段与 Project 字段。** 镜像字段保留跨 Project 可见性，但每个写入方和手动编辑都可能造成漂移，并需要一套对账政策。

**处理每个订阅的 pull request 事件或覆盖 `Start Date`。** 后续事件可以修补缺失日期，但会在工作开始后才分配日期或替换手动计划；因此初始化器保持仅 opened、仅空值。

## 影响

- 评审者与自动化获得 GitHub 的 stack 图谱、stack 级规则、CI 和原生合并状态。作者唯一的未堆叠链无需额外提示即成为官方 stack，而混合归属与冲突元数据保留人类决策边界。`gh stack sync` 可能短暂发布本地证据尚未完成的代码；受影响的 PR 在同步后的即时验证通过前保持不可合并。
- 意图、语义范围、Issue 的创建方式、优先级和运维触发器可以独立查询。维护者阅读变更和实时的标签描述，而不是从标题前缀或路径推断分类；当某个 kind 或不显然的 area 边界变化时，实时目录、本记录和政策执行必须一起变动，分类法迁移也带有显式的回填与核实成本。
- 重复的评审请求会把自动化管理的解决中 Issue 推进到 `In review`，即使 GitHub 仍报告着一个更早的阻塞评审；随后的请求修改评审把它退回 `In progress`；批准、评论、撤销、推送和移除评审者都不改变最近一条命令的状态。投影是事件驱动的，不会修复一个从未运行的事件；重放旧的工作流运行可能重放其旧命令，ProjectV2 在最新状态读取与变更之间也不提供原子的比较并交换——按 pull request 的工作流并发与人类归属守卫在不引入持久生命周期状态的前提下减少这些竞争。
- 规划元数据的范围是单个 Project 成员资格：同一 Issue 在另一个 Project 中可以有不同的值，`HDSH Issue Management` 之外的 Issue 没有 Project 本地的规划值。GitHub App 需要的是 Project 访问权限而非组织 Issue Fields 访问权限，字段重命名或类型变更会让工作流失败而不是回退。空值读取让重试幂等，但 Project 字段更新没有比较并设置的前置条件，因此两个同时到来的 pull request 可能都观察到空的 `Start Date`，最后一次变更胜出。
