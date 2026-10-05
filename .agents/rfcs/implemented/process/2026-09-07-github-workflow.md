# RFC: The GitHub workflow: native stacks, PR labels, and Issue lifecycle automation

Status: implemented

English | [中文](2026-09-07-github-workflow.zh.md)

## Problem

The GitHub side of the workflow has to answer four questions that neither code nor reviewer memory can hold. A dependent PR chain represented only by base branches has no official stack identity: landing it means merging one PR at a time, preserving intermediate branches, retargeting every child, and reconstructing afterwards whether the chain survived. Pull-request labels answer two independent questions — what kind of change the work makes and which durable domains it materially affects — and mixing those dimensions, or keeping synonymous plain and namespaced labels, makes queries ambiguous, while a closed area inventory forces new domains into inaccurate categories; Issues already carry a native Type and a separate source taxonomy, so reusing PR labels on them duplicates metadata. The Issue Project status records who owns the next step of resolving work, but GitHub's aggregate review state cannot represent that handoff: an earlier `CHANGES_REQUESTED` review remains effective after the author fixes the code and requests review again, and a monotonic projection cannot return an automation-owned Issue from `In review` to `In progress`. And planning metadata needs a home: organization Issue fields require a GitHub App permission separate from organization Projects, so storing values in both systems makes one policy depend on two independently administered permission sets.

## Decision

### Dependent PRs land as native GitHub stacks

Every same-repository chain of two or more dependent PRs uses GitHub's official stack object before landing. Live `PullRequest.stack` and `stackEntry.position` fields are authoritative. An unstacked chain whose PRs have one author is linked automatically in bottom-to-top order with `gh stack link`; mixed or unavailable authors require user confirmation. Missing native support and cross-fork chains hard-stop. Existing membership in conflicting stacks, or an official order that disagrees with the branch topology, requires user direction before any stack is dissolved or rebuilt.

"Land the stack" merges the complete official stack through `gh stack merge <stack-number> --yes --merge`. A partial landing requires an explicit boundary PR and merges the bottom prefix through that PR. The workflow never falls back to per-PR `gh pr merge` and manual retargeting. A direct native merge is all-or-nothing; a merge queue may process the selected PRs in separate groups, so every selected PR must independently reach `MERGED` before the landing is complete. After any rewritten push, current heads, unresolved review threads, approvals, mergeability, and checks are re-audited because earlier commit OIDs and inline anchors may be outdated. The [local Git workflow](2026-09-07-local-git-workflow.md) owns the refresh histories themselves — merge-forward checkpoints and lease-protected rebases — and the [stacked-PR landing skill](../../../skills/merging-stacked-prs/SKILL.md) carries the procedure.

### Labels: one kind, every material area

Every open or merged pull request carries exactly one canonical `kind/*` label and at least one materially affected `area/*` label. Closed pull requests that were never merged retain historical assignments but receive no invented classification. Operational labels may coexist without satisfying either dimension.

The kind set is closed and mutually exclusive:

| Kind | Meaning |
|---|---|
| `kind/feature` | Adds or intentionally changes behavior. |
| `kind/bug-fix` | Corrects incorrect behavior. |
| `kind/doc` | Makes documentation the dominant intent. |
| `kind/testing` | Changes tests or testing infrastructure without changing product behavior. |
| `kind/cleanup` | Preserves behavior while maintaining or simplifying implementation or repository process. |
| `kind/dependency` | Updates dependencies without another dominant intent. |

The kind records the dominant intent: accompanying tests, documentation, cleanup, or dependency movement do not override a feature or bug fix, and a new kind changes these rules and requires an explicit taxonomy and policy change. Repository policy rejects unsupported `kind/*` values.

Areas name durable product or engineering subjects rather than temporary initiatives, ownership, or every path touched incidentally. A pull request carries multiple areas when it changes distinct behavior or APIs, but never combines an umbrella and a narrower label for the same change. GitHub's live `area/*` names and descriptions own the current inventory, and the set is intentionally extensible: when no existing description honestly covers a durable, reusable domain, an agent may create a concise `area/<lowercase-kebab-case>` label without separate approval, must not create one for a single pull request, an incidental path, a temporary project, a status, or a person or team, and reports the new label and its rationale to the requester after applying it. Reusing an inaccurate area merely to avoid a justified addition is not acceptable.

Issues use the native Issue Type instead of `kind/*`, and their `area/*` labels remain optional. `source/*` labels record how an Issue was created and do not apply to pull requests. Priority, GitHub defaults, and workflow triggers remain independent operational metadata. Label migrations preserve meaning before removing aliases: add the canonical replacement, verify the labelable, then remove the obsolete assignment; a label is deleted only after no pull request or Issue still uses it, and unrelated labels are never replaced as a set.

### Issue Project status follows review events as commands

The Issue lifecycle workflow (`.github/workflows/issue-lifecycle.yml`) treats review webhooks as commands dispatched through the `hdsh policy` engine, invoked as `hdsh policy lifecycle --config .github/issue-management/config.json` with the event taken from `--event` or `GITHUB_EVENT_PATH`. `pull_request.review_requested`, including a repeated request, targets `In review`. `pull_request_review.submitted` targets `In progress` only when `review.state` is `changes_requested`; the submitted event remains necessary because a reviewer can request changes without an earlier review-request event. Approved and commented submissions run their lifecycle job but no-op — they never reach the Project token step, so they mint no write-capable token — and dismissed reviews are not subscribed.

Ordinary subscribed pull-request events remain forward-only implementation signals: they can move `Inbox`, `Backlog`, or `Ready` to `In progress`, but never move `In review` backward. Review-request commands can move any earlier active status to `In review`. Changes-requested commands can move earlier active statuses forward to `In progress` and can move `In review` back only when the latest status event for the target Project was written by the configured lifecycle actor; a human or unknown latest actor preserves the current status.

The status projection resolves only exact same-repository `Fixes`, `Closes`, or `Resolves` references. It does not alter terminal statuses, add an Issue with no Project status, depend on PR metadata validity, query `reviewDecision`, reconstruct review rounds, look up pull requests from Issues, or run a scheduled reconciler. The lifecycle workflow is unsubscribed from `pull_request.ready_for_review`; the policy workflow (`.github/workflows/issue-policy.yml`, `hdsh policy pr`) retains it because it owns required-check enforcement when a human pull request enters review.

### Planning fields live in the Project

The `HDSH Issue Management` Project owns `Priority` and `Start Date` as Project custom fields. Policy resolves both fields from the configured Project, rejects an Issue-backed field or the wrong data type, reads `Priority` from the Project item, and writes `Start Date` through `updateProjectV2ItemFieldValue`.

The policy workflow uses the repository `GITHUB_TOKEN` for REST Issue and pull-request reads, and a GitHub App token restricted to repository Issues and organization Projects read access for ProjectV2 queries; lifecycle mutations use the write-capable App token. User-account deployments replace the App with a classic PAT (`HDSH_PROJECT_PAT`, `project` scope only) for ProjectV2 while REST runs on `github.token`; the [user-account support RFC](../feature/2026-09-08-user-account-issue-policy.md) owns that flavor. The lifecycle workflow initializes `Start Date` only for `pull_request.opened`: it reads the pull request's live body, retains every same-repository reference that resolves to an Issue, converts `created_at` to a calendar date in the configured Project time zone, ensures the Issue is a Project item, and writes the date only when the current Project value is empty.

### The review loop

Review fixes land on the PR that introduced the defect before they propagate through dependent layers; the [stack review cookbook](../../../../docs/cookbook/responding-to-pr-review-on-a-stack.md) owns the propagation procedure. The [code-review skill](../../../skills/reviewing/SKILL.md) orients a reviewer to this repository's standards and the checks code alone cannot show, and the [pre-push checks skill](../../../skills/pushing/SKILL.md) owns evidence selection before publication. Skills carry procedure; this record carries the decisions they implement.

## Verification

`tests/policy/` pins the closed kind set, the exactly-one-kind and at-least-one-area rules, the Issue-side prohibitions, the event-to-command mapping, the repeated-review-request transition after a changes-requested command, the changes-requested regression, terminal protection, human-override preservation, the Project custom-field requirements for `Priority` and `Start Date`, separate credentials for repository and Project reads, the configured-time-zone date boundary, opened-only dispatch, empty-value writes, existing-value preservation, missing Project items, and the `updateProjectV2ItemFieldValue` mutation. The workflow files' subscribed events, the step-level gate on the token and board steps, the read-only Project token permissions, and the separate `ready_for_review` policy trigger are covered by review of the two workflow files. The landing procedure verifies native support, same-repository branches, live authors, official membership and order, merge range, and final merged state.

## Alternatives considered

**Keep branch chains as the only stack representation.** This preserves the manual procedure but gives GitHub no stack object through which to show order, enforce trunk rules across every layer, or merge a range atomically.

**Adopt native stacks while forbidding their rebase commands after review.** This keeps commit OIDs stable but disables the official synchronization path while a stack is under active review and leaves standalone PRs under a different policy.

**Automatically dissolve conflicting stacks.** This would let local branch inference override shared GitHub metadata and could disturb PRs or authors outside the requested chain; merged and queued entries cannot always be removed.

**Unprefixed labels.** Plain names reduce visual noise but do not identify whether a label classifies intent, domain, source, priority, or automation, and retaining plain and namespaced synonyms makes queries and policy enforcement ambiguous.

**One undifferentiated label set.** A label's presence would not prove that both intent and semantic scope were considered.

**A fixed area allowlist in repository policy.** Durable repository domains evolve; the `area/*` namespace stays mechanically recognizable while live descriptions carry the extensible inventory.

**Package- or path-derived areas.** Areas describe semantic impact across package boundaries, while changed paths include incidental tests, documentation, and support files.

**Kinds on Issues.** The native Issue Type already owns that classification; duplicating it as a label creates drift.

**Exactly one area per pull request.** Coherent changes can materially affect several independent APIs or behaviors, and dropping secondary areas hides affected scope.

**Derive status from `reviewDecision` or a reconstructed review round.** GitHub's aggregate can remain `CHANGES_REQUESTED` after a repeated review request, while a round reducer introduces reviewer and ordering semantics beyond the two explicit handoffs.

**Keep the forward-only projection.** Monotonic advancement protects later statuses but leaves an Issue in `In review` while the author implements requested changes.

**Apply every review command unconditionally.** This is the smallest event handler, but it lets automation overwrite a human-owned Project status; the latest target-Project status actor therefore guards the only backward transition.

**Subscribe the lifecycle to `ready_for_review` or add a debounce queue.** Ready status carries neither review handoff, while another queue adds latency and control-plane state without changing either command.

**Keep organization Issue fields for planning.** They make one value visible across Projects, but no workflow needs that scope and the GitHub App would require separate organization Issue Fields access.

**Dual-write Issue and Project fields.** Mirrored fields retain cross-Project visibility, but every writer and manual edit can create drift and requires a reconciliation policy.

**Process every subscribed pull-request event or overwrite `Start Date`.** Later events could repair missing dates, but they would assign dates after work starts or replace a manual plan; the initializer therefore stays opened-only and empty-only.

## Consequences

- Reviewers and automation receive GitHub's stack map, stack-wide rules, CI, and native merge state. A same-author unstacked chain becomes official without an extra prompt, while mixed ownership and conflicting metadata retain a human decision boundary. `gh stack sync` can briefly publish code whose local evidence is pending; the affected PRs remain blocked from merging until immediate post-sync validation passes.
- Intent, semantic scope, how an Issue was created, priority, and operational triggers are queryable independently. Maintainers read the change and the live label descriptions instead of inferring classification from title prefixes or paths; the live catalog, this record, and policy enforcement move together when a kind or a non-obvious area boundary changes, and taxonomy migrations carry an explicit backfill and verification cost.
- A repeated review request moves an automation-managed resolving Issue to `In review` even while GitHub still reports an older blocking review; a later changes-requested review returns it to `In progress`; approval, comments, dismissal, pushes, and reviewer removal leave the most recent command's status unchanged. The projection is event-driven and does not repair an event that never runs; replaying an old workflow run can replay its old command, and ProjectV2 offers no atomic compare-and-swap between the latest-state read and the mutation — per-pull-request workflow concurrency and the human-ownership guard reduce these races without durable lifecycle state.
- Planning metadata is scoped to one Project membership: the same Issue can hold different values in another Project, and an Issue outside `HDSH Issue Management` has no Project-local planning values. The GitHub App needs Project access rather than organization Issue Fields access, and a field rename or type change fails the workflow instead of falling back. The empty-value read makes retries idempotent, but Project field updates have no compare-and-set precondition, so two simultaneous pull requests can both observe an empty `Start Date` and the last mutation wins.
