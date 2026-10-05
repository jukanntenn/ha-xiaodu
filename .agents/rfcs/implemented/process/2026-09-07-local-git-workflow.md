# RFC: The local Git workflow: narrow hooks, worktree-local installs, deliberate history, and outgoing evidence

Status: implemented

English | [中文](2026-09-07-local-git-workflow.zh.md)

## Problem

Work on this repository happens in several linked worktrees of one clone, mostly by coding agents, and every stage of the local Git workflow has an obvious-but-wrong default. Every gate a contributor can imagine is a candidate for a pre-commit hook, yet each addition taxes every commit in every worktree; the full gate matrix (ruff, basedpyright, ty, pytest under the 100% branch-coverage requirement, the corpus-wide pairing check) takes long enough that contributors would start bypassing hooks, which is worse than running fewer of them. Git keeps one shared hooks directory per repository, so a repository-wide `core.hooksPath` lets a branch that changes `prek.toml` mutate hooking for every other worktree, lets two installers race, and lets `prek install` into `.git/hooks` silently cover only the main worktree. Running independent gates concurrently is the obvious way to cut wait time, but a home-grown parallel runner must own process management, output interleaving, cancellation, and failure aggregation that prek already ships. A PR base can advance while its current tip is being merged into the branch: restarting from the newer tip discards completed conflict resolution and validation, while rewriting an already-pushed merge erases reviewable history. Finally, pre-push checking, code review, and documentation audit all need the diff against the actual base, but `origin/<current-branch>` does not exist for a new worktree branch before its first push and misstates a stacked branch whose PR targets another feature branch; an incorrect range silently omits affected paths, and a three-dot committed diff says nothing about the staged, unstaged, and untracked layers.

## Decision

The local workflow is one policy with five parts: hooks stay narrow, hooks install per worktree, prek owns concurrency, branch history is chosen deliberately, and the outgoing change is measured by an explicit report.

### Local hooks are fast, staged-surface checkpoints

[`prek.toml`](../../../../prek.toml) installs `pre-commit`, `pre-merge-commit`, and `pre-push` hooks that run inside the uv-managed environment (`uv run --no-sync …`), so prek builds no separate hook environments. Pre-commit runs only checks whose cost is bounded by the staged surface: prek's builtin whitespace fixers (excluding pairing records and the frozen `.agents/rfcs/archived/` tree, whose bytes must stay stable), the staged pairing-record check (`hdsh pairing verify --cached` over staged `*.i18n.yaml`), staged `ruff check --fix` and `ruff format`, `git diff --cached --check`, the RFC format gate (`hdsh rfc verify`) and the frozen-archive gate (`hdsh rfc archive`), and the three document-corpus gates (`hdsh docs wrap`, `hdsh docs links`, `hdsh docs budgets`) when Markdown or the docs manifest is staged. Pre-push runs `basedpyright` over the whole tree. Fixer hooks that rewrite files exit non-zero so the caller re-stages and commits again.

Everything else belongs to CI: the full pytest run with the 100% branch-coverage gate, the corpus-wide pairing check, `ty`, and the platform matrix. A scoped green never substitutes for CI's exhaustive run, and adding a hook requires arguing that it is a fast staged-surface checkpoint, not merely useful.

### Hooks install worktree-locally

`hdsh worktree install` installs hooks into the worktree-private git directory rather than the shared one:

- The hooks directory is `<worktree-git-dir>/hdsh-hooks`, guarded by an ownership marker (`.hdsh-hooks-owned`) recording version, owner, and absolute path. The installer refuses to create, use, or overwrite a hooks directory that is not a regular directory it owns, and refuses multiply-linked or non-regular entries inside it.
- Per-worktree configuration requires `extensions.worktreeConfig` plus repository format 1. The installer validates the common config first — refusing dormant extensions, `core.worktree`, and `core.bare=true` — before migrating.
- `core.hooksPath` and the `merge.hdsh-pairing` merge-driver configuration are written as worktree-scoped config only. The installer refuses to mask an inherited value or replace a worktree-scoped custom value; `HDSH_PREK_ALLOW_HOOKS_PATH_OVERRIDE=1` is the explicit exception for user-owned inherited paths. Command-scoped config is never replaced.
- Installation is serialized by `hdsh-hooks-install.lock` in the common git directory, with stale-lock detection by PID and a fail-loud manual-recovery error. Every owned config write is rolled back if a later step fails, and `prek install --overwrite` runs with command-scoped `GIT_CONFIG_*` scrubbed from the environment.
- prek honors repo-local and worktree-local `core.hooksPath` natively, so its shims land in the worktree-local directory without extra glue.

### prek owns parallelism; gates stay side-effect-free

Each gate is safe for concurrent execution by construction: gates read the staged or working-tree plane, write at most their own outputs (the ruff fixers rewrite only their staged inputs), and hold no cross-gate locks. The installer's lock serializes only hook installation, never gate execution. A gate that cannot honor this contract declares `require_serial` in `prek.toml` — the whole-tree `basedpyright` pre-push hook does.

### Branch history is chosen deliberately

Merge-forward and rebase are both allowed refresh histories for standalone and stacked PRs, including after review. The [GitHub workflow](2026-09-07-github-workflow.md) owns how stacks are represented and landed, and the [stacked-PR landing skill](../../../skills/merging-stacked-prs/SKILL.md) selects between the two histories under the root `AGENTS.md`.

When merge-forward is chosen, each observed base tip gets its own merge checkpoint. If the base advances during the work, finish and validate the merge already in progress, commit it, and push it when the task authorizes a push; only then fetch and merge the newer base in a separate merge commit. A checkpoint within that merge-forward sequence is never abandoned or rewritten.

When rebase is chosen, a remote history rewrite uses an exact lease (`--force-with-lease=<branch>:<expected>`) or the lease-protected `gh stack` push path and aborts if the remote moved; raw `--force` is forbidden. Relevant checks run before publication; `gh stack sync` is the one exception because it fetches, cascade-rebases, and pushes as one operation, so every rewritten layer is validated immediately afterward and no affected PR merges until that evidence passes.

### The outgoing change is an explicit scope report

`hdsh scope` requires `--base <ref>`, accepts `--head <ref>` with `HEAD` as the default, and writes one versioned JSON report. It resolves both inputs to commits with ambiguity detection and requires one merge base before rendering. The report records the repository root without normalizing legal path whitespace, the input refs, the resolved base, head, and merge-base commit IDs, and sorted committed, staged, unstaged, and untracked path sets. Path records are split at raw NUL bytes and decoded as strict UTF-8; an invalid value aborts the report instead of substituting characters or collapsing distinct values.

Committed paths compare the resolved merge base with the resolved head; the dirty sets always describe the current worktree and index, even when `--head` names another commit. Every Git probe disables configured filesystem monitors and optional lock-taking; diff configuration cannot hide submodules or invoke external diff or text-conversion drivers, and rename detection is disabled so both sides of a rename remain visible.

The command never guesses or fetches a base, queries a hosting provider, or selects tests. Each calling workflow — the [pre-push checks skill](../../../skills/pushing/SKILL.md), code review, documentation audit — verifies the current remote or stack state, supplies the base explicitly, and uses the factual report as input to evidence selection or semantic review.

## Verification

Temporary-repository tests under `tests/worktree/` pin the installer's ownership marker, config validation and scoping, and install contracts, and `tests/scope/` pins explicit and stacked refs, every dirty layer, legal path whitespace, strict path decoding, inert probes, invalid refs, the deterministic schema, and unchanged refs, index, config, and status after reporting; pytest runs under the 100% branch-coverage gate. The hook set itself is configuration reviewed like code, and `prek.toml` stays small enough to read on one screen.

## Alternatives considered

**Run the full test suite pre-commit.** Commit latency would grow by an order of magnitude; contributors would bypass or skip hooks, losing even the fast checkpoints.

**Run the corpus-wide pairing scan pre-commit.** Pair records are already checked byte-exactly when staged; corpus-wide discovery and structure checks are unchanged by most commits and belong to CI.

**No local hooks at all.** The staged pairing-record check and whitespace hygiene catch exactly the classes of breakage that are cheapest to fix at staging time and most annoying to diagnose in CI.

**A shared hooks directory outside the repository.** One mutation surface for all worktrees and an install target outside the repository's ownership boundary; uninstalling or upgrading one worktree would silently change the others.

**Repository-global `core.hooksPath` in `.git/config`.** The same sharing problem with in-repository storage; linked worktrees would still inherit the main worktree's hook state.

**Git's default `.git/hooks` per worktree.** Linked worktrees do have private git directories, but nothing keeps prek's shims synchronized with `prek.toml` there, and the ownership marker is what makes an uninstaller safe.

**A repository-owned parallel gate runner.** It would duplicate prek's process pool, output demultiplexing, and cancellation semantics, and every hook author would have to understand them.

**Serialize every gate for determinism.** Output ordering is deterministic within each hook; cross-hook interleaving is cosmetic, and serial execution multiplies wall-clock time on every push.

**One aggregate script that runs all gates.** A single process hides which gate failed until it finishes, defeats fail-fast, and cannot be selected or skipped individually through prek.

**Abort a merge-forward and restart from the newest base.** This discards resolved conflicts and completed validation, repeats work, and removes a useful recovery point.

**Fold both base tips into one rewritten merge.** This hides the order in which conflicts were resolved and requires rewriting remote history if the first merge was pushed.

**Forbid rewriting reviewed branches outright.** A blanket prohibition also excludes the native `gh stack sync` workflow, whose cascading rebase updates each layer with lease protection, and would leave standalone and stacked PRs under different history policies.

**Require rebase for every refresh.** A linear history is useful, but merge checkpoints remain a valid choice when preserving completed conflict resolution and its recovery point matters more than compact history.

**An ad hoc diff command plus a prose fallback for scope.** This avoids a repository tool but leaves ordinary new-worktree and stacked-base topologies inconsistent across workflows, and it omits the dirty layers.

**Infer the base from the configured upstream.** An upstream may be `origin/main` before the first push, the same feature branch after a push, or a head branch whose PR targets another feature branch; no inference is correct for every topology.

**Query GitHub for the base inside the scope command.** This couples a local read-only report to one forge and to network credentials, yet still cannot resolve a branch with no PR.

**Generate required tests from changed paths.** Paths cannot establish behavior reached through configuration, dynamic loading, subprocesses, or workers; evidence selection remains judgment under pre-push checking.

**Report the current branch and upstream and maintain a parallel human renderer.** Callers already verify branch and base state before invocation, no consumer uses those fields, and formatted prose duplicates the JSON schema without improving path completeness.

## Consequences

- Commits stay fast and the hook set fits on one screen; CI owns the exhaustive gate matrix, so a green local hook run is never evidence of overall health.
- Each worktree's hooks match its own `prek.toml`; switching branches in one worktree never affects another, and deleting a worktree removes its hooks with it. The installer fails loud on any precondition it cannot verify, leaving the previous hooking intact; the lock lives in the common directory and is removed on release.
- Gate wall-clock time is bounded by the slowest single gate, not their sum; gate independence is a code-review requirement, and prek upgrades can change scheduling without repository changes.
- A PR can carry several base-merge commits when its base advances repeatedly; completed work remains reviewable and recoverable, and merging a newer base changes the combined tree, so the relevant checks run again before the next push. A rebase can invalidate commit hashes, approvals, and comment anchors, so every rewritten push carries a live review and check re-audit.
- The explicit base makes an incorrect base possible but visible: both input refs and all three resolved commit IDs appear in the report, and callers pay the small cost of verifying and fetching the live base first. The string schema deliberately cannot represent non-UTF-8 path bytes; a repository containing them must rename those paths before it can produce a report.
