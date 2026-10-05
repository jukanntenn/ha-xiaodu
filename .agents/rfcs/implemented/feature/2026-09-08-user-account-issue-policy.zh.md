# RFC: 议题策略引擎的个人账户支持

Status: implemented

[English](2026-09-08-user-account-issue-policy.md) | 中文

## 问题

议题策略（Issue/PR policy）引擎最初是照着三个组织专属的 GitHub 机制写成的：ProjectV2 GraphQL 入口 `organization(login:)`、作为 Issue 分类载体的原生 Issue Type、以及持有组织 Projects 权限的 GitHub App 作为 Project 凭据。个人账户所有的仓库三者皆无——GraphQL 的 `organization` 字段只解析组织；个人账户仓库根本没有原生 Issue Type，每个 Issue 都会永远过不了分类校验；GitHub App 也无法被授予用户所有 Project 的访问权：只有带 `project` scope 的 classic PAT 能读写它们，而 `GITHUB_TOKEN` 对两种归属的 Project 都不可见。本框架的受众包含个人账户仓库——本仓库自身就是一个——因此同一套规则必须能治理两种账户，且「部署形态（deployment flavor）差异」与「策略变更」的界线要落在显式之处，而不是散落的条件分支里。

## 决策

### 一个引擎，两种部署形态

`config.json` 显式声明账户种类：`owner`（由 `organization` 更名）加上 `accountType`，在加载时对照封闭集合 `organization` | `user` 校验。GraphQL 入口、分类载体、工作流凭据路径——所有依赖账户的分支都由这同一个真源驱动；写错 `accountType` 会在 Project 解析处显性失败，绝不静默。

### GraphQL 入口跟随账户种类

Project 查询同时声明两个顶层入口——`organization(login: $owner) @include(if: $isOrganization)` 与 `user(login: $owner) @include(if: $isUser)`——二者的 `projectV2` 选择集完全相同；客户端取用形态启用的那个账户块。一份查询，一份 ProjectV2 契约。

### 分类：同一分类学，载体随平台

五个名称的分类学（Idea、Feature、Bug、Research、Task）不变。组织部署沿用原生 Issue Type。个人部署以恰好一个 `type/*` 标签（`type/idea` … `type/task`）承载它；`classification_from_labels` 在快照边界把标签载体归一化为规范名，`validate_issue` 校验的是这个与载体无关的值。组织账户的 Issue 不得携带 `type/*` 标签——那是原生字段旁的影子分类学——而两种形态的 pull request 都不得携带它：`type/*` 与 `source/*` 同为 Issue 专属命名空间，镜像 Issue 侧的 `kind/*` 禁令。

### 凭据跟随形态

组织部署不变：一个 GitHub App（Issues 与 Pull requests 读写、组织 Projects 读写）为政策工作流铸造 Project 读令牌，为生命周期工作流铸造 REST 加 GraphQL 令牌。个人部署无法授予 App Project 访问权，因此 REST——含审计评论——走 `github.token`（marker 查找本就期待的 `github-actions[bot]` 身份），ProjectV2 GraphQL 走只带 `project` scope 的 classic PAT，以 `HDSH_PROJECT_PAT` 存储、由专职机器账号（machine account）持有。每个工作流从检出的 `config.json` 解析形态，匹配的凭据缺失时以点名错误显性失败；后续 `||` 令牌选择由该解析步骤证明，不是静默兜底。

### 身份模型

开发者身份——人及其绑定的 agent——以所有者账户提交 pull request。机器账号承担两项职责：其 `project` scope PAT 驱动看板自动化，使 Project 状态写入的执行者（actor）区别于每一个人；以及过渡性地，由人在浏览器端以它 review 和 approve pull request——因为唯一维护者不能批准自己的 PR（Pull Request），而第三个专职评审账号不值得其管理成本。两条运行纪律维持语义完好：手工看板移动只以所有者本人进行（机器账号拖动会伪装成自动化写入、从而可被回退）；机器账号的任何 repo scope 令牌永不存在于 CI 或本地——PAT 只有 `project` scope 时，该登录名下的每次批准必然是人的行为。

## 验证

`tests/policy/` 钉住封闭的 `accountType` 集合与更名的 `owner` 字段、选择 organization 或 user 入口的查询变量、user 入口的 Project 解析、快照边界上标签到规范名的归一化、组织账户的 `type/*` 禁令、pull request 的 `type/*` 禁令，以及不变的五名分类学。两个工作流文件的形态解析步骤、凭据缺失失败、条件化令牌铸造，以及个人部署的 `github.token` REST 路径，由对工作流文件的评审覆盖。首次实机演练：本仓库在 `jukanntenn` 账户上的 Issue 与 pull request 流程。

## 备选方案

**只支持组织，并文档写明「请使用组织」。** 放弃框架面向的个人账户受众；本仓库也无法吃自己门禁的狗粮。

**每种形态一个 client 类。** `ProjectV2` 只有一种形状；为一个字段的差异复制全部快照与变更逻辑。

**从 API 自查账户种类而非配置。** 规则是快照上的纯函数，看不见线上事实，形态会获得一个能与配置不一致的第二真源；一个经过校验的字段失败得更响、更早。

**两种形态都用 `type/*` 标签承载分类。** 统一，但在原生 Issue Type 免费存在之处放弃了它——列表过滤、类型视图——在两者皆备处用弱载体替换强载体。

**以 marker 评论作为状态执行者日志（markpost 的设计）。** 读取 GitHub 自有的 `PROJECT_V2_ITEM_STATUS_CHANGED_EVENT` 执行者无需在 Issue 上留日志评论，且一旦 PAT 属于机器账号便同样成立；marker 是对「PAT 属于人类」的补偿，而上述身份模型已经避免了这一点。

**个人账户上用 GitHub App 做 REST、再加 PAT 做 GraphQL。** 两个凭据换不来任何额外保证——看板写入的执行者仍是 PAT 的账户——而 `github.token` 让 REST 停留在仓库范围、零额外配置。

**第三个专职评审与批准账号。** 干净的归因（批准永不显示为 bot 登录名）不值得为唯一维护者多养一个要安全保管和轮换的机器身份；`project`-only PAT 规则用排除法恢复了同样的保证。

## 后果

- 个人账户仓库可以采纳完整的治理门禁——看板自动化、分类、标签分类学、生命周期投影——唯一新增凭据是一枚 classic PAT，范围仅限 Projects，读不到任何仓库内容（公共仓库；私有使用方加 `repo`）。
- 个人账户上分类由标签承载，策略因此无法使用 GitHub 原生的类型过滤：程序化创建 Issue 设的是标签而非 GraphQL type id，接收模板的前置键是 `labels: type/*` 而非 `type:`。
- 机器账号的浏览器职责把人类决策记录与 bot 登录名混在一起：批准显示在机器账号名下，「批准必是人做的」这一保证依赖于不存在任何 repo scope 的机器令牌——这是运行纪律而非平台机制。未来的专职评审账号，或反向极性（机器执笔、人类批准），都能不改引擎地恢复归因。
- 组织部署保持单一 App 身份做 REST 与看板写入；App 的权限面包含 Pull requests（读），供生命周期 REST 读取使用，此前的记录低估了这一点。
- 每个依赖账户的分支都出自同一个配置字段；更换账户种类的部署同时修改 `owner` 与 `accountType`，工作流的凭据检查以点名的缺失 secret 失败，而不是下游的令牌错误。
