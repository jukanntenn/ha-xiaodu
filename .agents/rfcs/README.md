# RFCs

English | [中文](README.zh.md)

One kind of design doc lives here. An **RFC** records a decision or proposal that affects this codebase — the *why* and *what we gave up*, the parts code and docs can't carry. This file defines where RFCs live, when to write one, and [the in-file format](#the-file-format).

## Layout and naming

Every RFC has two axes, both encoded in its **path** — `{lifecycle}/{class}/yyyy-mm-dd-topic-title.md`:

- **Lifecycle** (the top-level folder) is the RFC's status, and an RFC moves between folders as that status changes:
  - **`proposed/`** — proposals reviewed before implementation; not yet built (or only partly).
  - **`implemented/`** — the decision shipped. The file records what was decided and what was rejected, and is **kept current with what actually shipped**: when the code later moves a file, renames a module or gate, or changes a key/default, the RFC is updated in the same change to match (facts only — paths, names, structure — not the decision itself). See [implemented/AGENTS.md](implemented/AGENTS.md).
  - **`rejected/`** — the proposal was considered and declined. Keep it only while its rationale prevents a tempting, meaningful mistake; otherwise delete the complete triplet.
- **Class** (the nested folder) is the *kind* of decision — see [Classification](#classification) below.

The date in the filename is when the topic was **first proposed** (per git history). Cross-references between RFCs use relative markdown links (`[topic](../../implemented/architecture/2026-…-….md)`) — never bare prose or numbers — so they survive moves between folders and stay checkable in review.

The active lifecycle tree is the working inventory: browse its lifecycle/class folders or search the repository. Do not add a centralized `INDEX.md` or any other generated index. Low-future-value implemented records move to the separate frozen [`archived/`](archived/AGENTS.md) tree described below.

<a id="classification"></a>

## Classification

Each RFC belongs to one path-encoded class from the closed set the format gate enforces; the gate rejects other folders. Adding a class requires updating the canonical set and this section.

| Class | What it covers |
|---|---|
| `feature` | A new user- or model-facing capability. |
| `bug-fix` | Corrects a defect or closes a gap a postmortem surfaced. |
| `simplification` | Removes code, behavior, or surface area without adding a capability. |
| `architecture` | A structural decision about the **shipped source** — how modules relate, what the runtime vocabulary is. |
| `process` | Tooling, policy, or workflow **around** the code — gates, the package manager, CI — not runtime behavior. |
| `testing` | Test infrastructure and strategy. |

The `architecture` / `process` line: **architecture** is about the source we ship; **process** is the surrounding tooling and workflow. (`refactor` is deliberately absent — it overlaps `simplification`, whose discriminator, "does observable behavior change?", already covers it.)

## Archiving and deletion

Archive an implemented RFC when the shipped decision is complete and its rationale is unlikely to guide future work. Keep it active when its alternatives, ownership boundary, negative guarantee, durable-format semantics, security rule, or reintroduction condition remains useful. Never archive a proposed RFC: reject an obsolete proposal. Keep a rejected RFC only while it prevents a plausible mistake; otherwise delete its English, Chinese, and sidecar files together.

Supersession is checked while a new RFC is written, using the calibrated [`archiving-rfcs`](../skills/archiving-rfcs/SKILL.md) workflow rather than word count, age, or a target quota: search the active tree for older records covering the same decision or mechanism, classify every full or partial supersession, archive every qualifying implemented triplet in the same PR, and keep partial supersessions active and cross-linked.

The archive is path-encoded as `archived/{class}/yyyy-mm-dd-topic-title.md`; `implemented` is deliberately absent because only implemented RFCs can enter it. An archival change moves the complete English/Chinese/sidecar triplet, retains `Status: implemented`, inserts the same `Archived: YYYY-MM-DD` line immediately below that status in both language files, re-records the sidecar, and repairs or deletes inbound links. These are the only permitted content changes during archival.

Once sealed, every archived triplet is permanently frozen. Do not edit, translate, reformat, update, move, or delete it, and do not treat it as authority for current behavior. The pairing gate and the format gate exclude the archived tree from their corpora, and active prose may still link into an archived RFC when it intentionally cites history. `hdsh rfc archive` enforces the closed class tree, complete triplets, sealed headers, sidecar hashes, and the append-only frozen-content manifest; `hdsh rfc seal` appends new artifact hashes after proving every existing seal unchanged. The manifest, not git history, is the seal source — history rewriting and shallow checkouts make commit ancestry unreliable as a local seal source — and sealing is a separate command, following the pairing domain's `verify`/`record` precedent that mutation is always an explicit command.

## When to write one

Every non-trivial change MUST add or update at least one RFC in the same PR. A change is non-trivial when it alters behavior, architecture, a contract shared across files or modules, process or tooling, testing strategy, an on-disk or configuration format, or another decision a maintainer may reasonably revisit. A proposal for substantial future work starts in `proposed/`; a decision already made starts in `implemented/`. Pick the class folder that matches the decision (see [Classification](#classification)).

Updating the RFC that already owns the decision satisfies the rule; do not create a duplicate. Only a purely mechanical or local edit with no change to behavior, contracts, structure, process, or rationale is exempt. An RFC is never edited into a *different decision*: supersede it with a new one, and keep both RFCs cross-linked unless the old one is later fully consolidated under the rule below. Editing an `implemented/` RFC to track where its existing decision lives is required, not forbidden; see [implemented/AGENTS.md](implemented/AGENTS.md).

An implemented RFC that is fully superseded may be consolidated into the current owning RFC and deleted. Before deletion, the owner must preserve every unique rationale, alternative, consequence, required verification, and named coverage gap; repair every inbound link; and delete the Chinese counterpart and consistency record in the same change. Partial supersession does not qualify: keep both RFCs cross-linked and update every fact that remains current. Consolidation must not rewrite the old file into its opposite or rely on git history as the only copy of rationale.

A feature-addition RFC may be consolidated into the later removal RFC only when the feature is absent from production code, configuration, on-disk formats, and compatibility behavior; no current documentation presents it as available; and no test exercises it as supported behavior. Removal rationale and tests that verify absence may remain. The removal owner preserves the original motivation, why it no longer justified the feature, alternatives to full removal, the capability given up, conditions for reintroduction, and verification of complete absence. Obsolete implementation inventories and tests that only verified the deleted behavior are not current verification evidence. Removing one implementation, default, or presentation is partial supersession, as is any surviving durable data or compatibility handling.

<a id="the-file-format"></a>

## The file format

Every active RFC follows one in-file format, enforced by `hdsh rfc verify` (also a pre-commit hook). Archived RFCs retain the format they had when sealed plus the archive-date line above.

### The header block

The first three lines of every RFC are exactly:

```markdown
# RFC: <title>

Status: <status>
```

followed by a blank line. The `Status:` value is one of three forms, and must agree with the lifecycle folder the file sits in — the gate cross-checks them:

- `Status: proposed`
- `Status: implemented`
- `Status: rejected — <why, in one line>`

The status carries no dates and no parentheticals: the filename holds the first-proposed date, git holds everything else, and an "accepted in amended form" note is body content (state the amendment where the decision is stated). The rejection reason is the one status with content, because a rejected RFC's verdict is the fact readers come for.

### The body skeleton

Every RFC opens its body with `## Problem` — the motivation, written to stand without the solution. What follows depends on the lifecycle; recurring sections use these canonical names and nothing else, while genuinely bespoke technical sections (gate behavior, configuration surfaces, verification) remain free-form between the required ones.

#### `proposed/`

```markdown
## Problem
## Proposal
…bespoke sections…
## Alternatives considered
## Acceptance criteria
## Risks
```

`## Proposal` is the intended change and may legitimately speak in the future tense — plans, migration steps, and open questions belong here while the work is unbuilt. `## Acceptance criteria` says what observable state means done. `## Risks` covers both what could go wrong and what the change knowingly gives up.

#### `implemented/`

```markdown
## Problem
## Decision
…bespoke sections…
## Alternatives considered
## Consequences
```

`## Decision` describes shipped reality in the present tense, and the whole file is kept current with it per [implemented/AGENTS.md](implemented/AGENTS.md). `## Consequences` records what the trade-off cost **and** bought. Proposal-era headings are spec-speak here and the gate rejects them: `## Proposal`, `## Plan`, `## Migration plan`, and `## Acceptance criteria` may not appear in an implemented RFC. A `## Testing`, `## Deferred`, or `## Related` section is fine where it states present-tense fact.

#### `rejected/`

A rejected RFC is the proposal, frozen: it keeps whatever proposal-time sections it had (including `## Acceptance criteria` or `## Plan`), and the verdict lives on the `Status:` line. Only the header block, the `## Problem` opener, a `## Proposal` section, and the Alternatives-considered mandate below apply.

### Alternatives considered — mandatory

Every RFC carries an `## Alternatives considered` section: each genuine alternative and why it lost, one bold-led paragraph per alternative or a `### Why not <X>?` subsection per contested one. Alternatives are recorded, never invented. A decision recorded without what it beat invites re-litigation — the failure RFCs exist to prevent.

### Moving between lifecycles

Moving a file between lifecycle folders means updating the `Status:` line and re-satisfying that folder's skeleton in the same change — the gate fails the move otherwise. Concretely, `proposed/` → `implemented/` rewrites `## Proposal` into a present-tense `## Decision`, folds `## Acceptance criteria` and `## Risks` into `## Consequences` (or a present-tense `## Testing`/`## Verification` section for what now pins the behavior), and drops plans in favor of what shipped — the rewrite [implemented/AGENTS.md](implemented/AGENTS.md) requires, made mechanical. `proposed/` → `rejected/` only adds the reason to the `Status:` line and freezes the file.

### Chinese counterparts

A `.zh.md` counterpart mirrors its English sibling's structure section-for-section under the [i18n contract](../../docs/i18n/README.md); the machine-checked header tokens (`# RFC: ` and the `Status:` line) stay in English verbatim. The format gate skips `.zh.md` files — the pairing gate checks their consistency.
