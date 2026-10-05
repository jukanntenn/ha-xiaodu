# 双语文档

[English](README.md) | 中文

本仓库以英文开展工作，文档的读者则包括项目内外的人与 agent（智能体），因此范围内的每篇文档都维护为一对英文／简体中文文档，两种语言同权。本页定义配对约定、检查、范围与排除规则；[translation-rules.md](translation-rules.zh.md) 定义如何翻译；[terminology.md](terminology.md) 是术语真源。agent 的日常工作遵循 [docs/AGENTS.md](../AGENTS.md) 中的轻量路径；扩展版 [.agents/skills/translating-docs](../../.agents/skills/translating-docs/SKILL.md) 工作流仅在用户显式调用时可用。

<a id="the-pairing-contract"></a>

## 配对约定

- **两种语言同权。** 一篇文档可以先用任一语言撰写和评审（先写中文的 RFC（决策记录）与先写英文的一样正当），另一侧由它翻译而来。两个文件谁也不高于谁；约束它们的是二者必须说同样的话。
- **一对文档是三个同目录文件。** 英文 `foo.md`、中文 `foo.zh.md`，加一份一致性记录（consistency record）`foo.i18n.yaml`，都在同一目录。不用语言目录，不用独立翻译仓库，不用中英混排的单文件。配对必须整体合并：PR（Pull Request）永远不会只带一种语言而缺其余两个文件。
- **一致性记录。**`foo.i18n.yaml` 保存两侧文件在上一次被确认「说同样的话」时各自的完整 Git blob hash：

  ```yaml
  foo.md: 3f786850e387550fdab836ed7e6dc881de23001b
  foo.zh.md: 89e6c98d92887913cadf06b2adb97f26cde4849b
  ```

  用 blob hash 而不是 commit hash，这样同一个 PR 里改动的文件也能算出记录（`git hash-object foo.md`），一致性是纯内容比较。重录会先把这些快照存入本地 Git 对象库再写下记录，未提交的 worktree 内容也不例外；它还会在内容寻址的 `refs/hdsh/pairing/snapshots/` ref 下固定每个不同的已存 blob，使垃圾回收无法让已记录的恢复指针失效。记录的 hash 能还原任一侧上次确认时的确切文本（`git cat-file -p <hash>`），所以失去同步的配对是「按被改一侧的 diff 最小化地修补另一侧」，从不整篇重译。日常工作会直接完成这份修补；用户显式调用扩展工作流时，可改由 `hdsh pairing brief <pair>` 以能安全对齐的最窄粒度汇集这次更新，并由 `--apply` 在结构校验后拼接仅涉及围栏代码块的改动（[briefed-updates RFC](../../.agents/rfcs/implemented/process/2026-09-07-briefed-minimal-translation-updates.zh.md)）。两侧对齐后，`hdsh pairing record <pair>` 重新记录两个 hash；那份 YAML diff 就是「确认一致」这个动作本身，可以被评审，也正因如此，`hdsh pairing record` 要求点名你确认过的配对（`hdsh pairing record --all` 是显式的全语料形式），裸调用会被拒绝：它会悄悄放过语料中每一对已经漂移的文档。

  当两个分支都包含同一配对的有效确认时，`hdsh-pairing` Git 合并驱动（merge driver）只会在 Git 默认文本合并能分别干净合并记录所指的英文三方 blob 与中文三方 blob，且合并后的配对仍保留必需的语言切换行、链接 locale 与结构签名时，才组合出一份新记录：中文侧必须保留指向英文的反链，普通撰写的英文源必须保留指向中文的链接，manifest `generated` 清单内的生成英文源不作此要求。该驱动由 `.gitattributes` 中针对 `*.i18n.yaml` 的 `merge=hdsh-pairing` 声明，并由 `hdsh worktree install` 注册到当前 worktree。任何驱动无法验证的结构都保留为普通冲突；`hdsh pairing merge --resolve` 会对已经停止的合并执行同一套遇错即保留冲突的操作：暂存每份可安全生成的配对记录，并在还有其他配对冲突时以非零状态退出。没有 `.gitattributes` 声明时驱动永不运行，记录按纯文本合并：不相邻的逐行改动干净组合但无结构校验，同条目改动以普通文本冲突，配对门禁在提交与 CI 兜底每一种情形。[双语配对门禁 RFC](../../.agents/rfcs/implemented/process/2026-09-07-bilingual-pairing-gate.zh.md) 负责记录该机制与备选方案。
- **语言切换行。** 中文文件一律在 H1 标题后立即以 `[English](foo.md) | 中文` 链回英文，普通撰写的英文文件在同一位置以 `English | [中文](foo.zh.md)` 互链；两个标签位都可写 `中文` 或 `简体中文`，门禁两者皆收、风格规则择一；manifest `generated` 清单内的生成英文源省略此行，以便与生成器输出逐字节一致，其中文对侧仍链接回英文。发布到 GitHub 以外位置的 README（例如 PyPI 项目元数据）可以改用 manifest `public_blob_root` 前缀为同一对侧文件配置的绝对 URL，使切换行在该位置仍可访问。
- **结构与另一侧一一对应。** 标题深度与顺序、列表类型、有序列表起始编号、列表项数量、表格行列数、保留原样 query/fragment 后缀的语义链接目标（绝对文档 URL 按其 `.md` 锚点形态比较），以及逐字节一致的代码块在配对两侧一一对应；由 `<!-- BEGIN GENERATED ... -->`／`<!-- END GENERATED ... -->` 标记界定的生成区块，除配对文档 locale 路径（比较前归一化为配对锚点）外必须逐字节一致。相对文档链接的目标属于活跃双语语料时，英文侧使用其 `.md` 路径，中文侧使用其 `.zh.md` 路径。该范围内缺少对侧属于配对完整性错误，不得回退；范围外的相对目标按英文锚点形态比较——`.zh.md` 目标与其 `.md` 对侧等价——因此在范围外遵循每侧 locale 约定不会使配对发散。完整保持规则见 [translation-rules.md](translation-rules.zh.md)。本仓库的 Markdown 约定对 `.zh.md` 文件原样生效：一个段落一个物理行（`hdsh docs wrap`）、相对链接必须可解析（`hdsh docs links`）、文件末尾恰好一个换行。

## 门禁：hdsh-pairing-verify

`hdsh pairing verify` 机械地强制执行这份约定。本仓库没有聚合式的文档门禁：prek 以暂存记录形式提供快速本地检查点，CI 运行全语料配对检查与 RFC 格式门禁：

1. 范围内的每篇文档都有完整配对。发现 README 时只看文件名且不区分大小写，并覆盖任意目录，因此今后新增的目录无需再修改 manifest（元数据清单）即可纳入语料。
2. 任何已存在的配对产物都完整且一致：三个文件齐全、每一侧的当前 blob hash 等于记录值（改了任一侧而没重新确认配对就变红）、中文侧和所有普通撰写的英文源都带语言切换行（manifest `generated` 清单内的生成英文源除外）、每条普通相对文档链接都使用源文件一侧对应的目标 locale，且结构签名按序一致：标题深度、逐字节一致的代码块（信息字符串与内容）、表格行列数、列表类型、有序列表起始编号、列表项数量，以及除切换行之外保留原样 query/fragment 后缀的语义链接目标；生成区块还须在配对文档 locale 路径之外逐字节一致。
3. 列为 `excluded` 的文件完全没有 `.zh.md`，也没有 `.i18n.yaml`。冻结的 `.agents/rfcs/archived/` 目录树是发现阶段排除项；翻译维护绝不能重写它。

`hdsh pairing list` 打印范围内每篇文档的当前配对状态（missing、out-of-sync 或 ok）。它从不失败；其中 missing 与 out-of-sync 行指出普通检查会拒绝的违规。

`hdsh pairing verify <pair...>` 只检查被点名的配对——配对的三个文件中的任意一个（或其裸词干）都能点名它——因此更新循环几秒内就能验证自己的配对，而不必重新扫描全语料。`--cached <pairs...>` 检查被点名配对在暂存区中的确切字节；prek 钩子会在每次提交前对已暂存的 `.i18n.yaml` 记录运行它。CI 运行的是无参数的全语料形式；限定范围的绿灯在 PR 层面永远不能替代它。

这个门禁带来的实际规则是：**当一个 PR 修改了已配对文档的任一侧时，同一个 PR 在术语指导下直接一次完成对侧文件的更新，并用 `hdsh pairing record <pair>` 重新记录配对**。留下失去同步的配对的 PR 会在 CI 变红。

门禁的限制很明确：**门禁通过意味着这组文档在当前内容上的一致性得到了确认，不代表确认本身正确可靠。** 它检查 hash 与 Markdown 结构；它无法判断两侧是否在说同样的话，也无法判断措辞是否准确、术语是否得当、行文是否自然；这部分约定由评审者把关，见 [translation-rules.md](translation-rules.zh.md)。重新记录了 hash 但另一侧翻得潦草的配对能通过门禁；它不得通过评审。

## 范围与排除

**范围**：树中任意位置的全部 README、根目录的 `ADOPT.md` 消费方手册、`docs/**` 下的全部文档，以及 `.agents/rfcs/**`（RFC 目录树）下的全部文档，加上 manifest `roots` 列出的子树，再减去下文的 `excluded` 与 `governed` 条目。依赖目录、缓存目录、构建产物目录、vendored（第三方源码）目录，以及 `src/hdsh/adopt/templates/` 下的打包接入镜像，只在发现阶段排除，不属于翻译源文档。

**排除**（永不配对，门禁拒绝为它们建 `.zh.md` 或 `.i18n.yaml`）。下列 agent 指令与翻译记忆文件是门禁自带的语料常量，manifest 不再为它们列条目：

- 树中任何 `AGENTS.md`：agent 指令，按类规则只以英文维护——manifest `roots` 子树因此无需逐文件打 `governed` 豁免；根 `AGENTS.md` 同样不在语料范围内。
- [terminology.md](terminology.md) 与 [style-samples.md](style-samples.md)：前者是中文侧的术语参考，后者本身即中英对照，配对检查对二者都没有意义。
- `.agents/rfcs/archived/`：整个冻结的档案目录树，封存的历史记录仅供引用，绝不编辑、翻译或重新记录。

**统一要求**：当前及今后纳入范围的每篇文档，合并时都必须构成完整的双语配对（bilingual pair）。[.hdsh/pairing.manifest.json](../../.hdsh/pairing.manifest.json) 只包含一个可选的 `excluded` 数组、一个可选的 `generated` 数组（后者列出免于英侧切换行的生成英文源）、一个可选的 `governed` 数组（命名由本仓库自行治理的双语内容：译文可以存在，门禁完全不看）、一个可选的 `roots` 数组（以尾斜杠子树前缀把语料扩展到标准范围之外）和一个可选的 `public_blob_root` http(s) URL 前缀（接受绝对形态的切换行链接）——解析器拒绝任何其他字段——不存在逐文件推进清单、日期分界或 README 专用政策类别。

## 分工

日常更新对侧文件时，负责处理的 agent 会先加载 [terminology.md](terminology.md)，再直接一次性完成；它不会生成简报、执行单独的翻译评审轮次，也不会委派给 subagent。扩展版 [translating-docs](../../.agents/skills/translating-docs/SKILL.md) 工作流保留这些较重的机制，仅供用户显式调用；恢复同样直接：用 `git cat-file -p <hash>` 还原上次确认的文本，按被改一侧的 diff 最小化修补对侧文件。门禁负责检查配对是否完整、记录的 hash、两侧切换行（manifest `generated` 例外）、链接 locale、生成区块一致性以及结构签名；翻译质量、术语和签名未涵盖的结构要求仍由评审把关。
