# RFC: Bilingual documentation pairs and the pairing gate

Status: implemented

English | [中文](2026-09-07-bilingual-pairing-gate.zh.md)

## Problem

This repository's documentation is read by people and agents in both English and Chinese. Maintaining a second language by hand, with no mechanism, is how translations rot: one side moves on, the other silently lies, and no gate notices. Three narrower problems follow from any mechanical answer. A bilingual pair references other documents, and if both sides used identical link paths a Chinese reader would be bounced onto English pages mid-document, while arbitrary links would give the structural comparison no way to treat the two sides' links as the same link. A pair's consistency record changes on every branch that edits the pair, so when two such branches merge, Git textually merges two hash records into garbage that names blobs which never existed together, and the gate then reports a drift that is really a merge artifact. And the counterpart update itself has a tempting wrong default: re-translating a whole document discards reviewed phrasing and drifts established terminology, while loading a whole guidance corpus for a two-line edit taxes exactly the behavior the contract wants — bringing the counterpart along in the same PR.

## Decision

### Paired sibling files with equal authority

A documentation pair is three sibling files: English `foo.md`, Chinese `foo.zh.md`, and a consistency record `foo.i18n.yaml`. Neither language is canonical — a document may be authored and reviewed Chinese-first and translated afterwards, or the reverse; what binds the pair is that both sides must say the same thing, and pairs merge whole (both languages plus the record, never one alone). The owning contract is the [i18n README](../../../../docs/i18n/README.md).

`foo.i18n.yaml` holds the full git blob hash of each side as of the last confirmed-consistent state. An edit to either side without re-confirming the pair is then mechanically detectable as a pure content comparison — no history lookup — and the hashes are computable for files edited in the same PR, which a commit-hash record is not. Re-recording (`hdsh pairing record <pair>`, which requires naming the confirmed pairs; bulk re-record is an explicit `--all`) produces a reviewable yaml diff, so confirming consistency is an explicit, visible act in the PR. Recording first stores both snapshots in the local object database and pins each stored blob under a content-addressed ref in `refs/hdsh/pairing/snapshots/`, so a recorded recovery pointer survives garbage collection and even never-committed working-tree bytes stay recoverable.

### The gate

`hdsh pairing verify` (hook id `hdsh-pairing-verify`) enforces that every discovered, non-excluded source has a complete pair; that every existing pair is complete and consistent (both hashes match, the Chinese side and every authored English source carry their language switchers, structural signatures identical); and that excluded files carry no `.zh.md` and no record. The structural signature compares heading depths in order, byte-identical fenced code blocks, table row and column counts, list kind, ordered-list start, and item counts, and every link's semantic target with its exact query or fragment suffix; the switcher line is excluded because its grammar admits exactly one link, and generated regions compare after each side's paired-document locale paths normalize to the pair anchor. The manifest `.hdsh/pairing.manifest.json` contains only explicit exclusions, the `generated` array of English sources exempt from the English-side switcher, and the optional `public_blob_root` URL prefix accepting absolute-form switchers, so no requirement can bypass discovery and receive a weaker check.

Scope is every README (case-insensitive basename) plus `docs/**` and `.agents/rfcs/**`, with dependency, virtual-environment, and build-output trees and the frozen `.agents/rfcs/archived/` tree outside discovery; root-level policy documents (recognized by the `CONTRIBUTING`, `BRAND_GUIDELINES`, and `SAFETY` basenames) participate in the same rules even though they sit outside documentation directories; this repository currently carries none. Every document in scope requires a complete pair from creation: there is no per-file rollout state, date cutoff, or README-specific class. Generated English sources are named in the manifest's `generated` array: they pair without the English-side switcher (a generator emitting that line would fail its own freshness check) while their Chinese counterparts still link back; this repository currently lists none.

Scoped invocations serve the update loop: a check named with pair paths touches only those pairs (any of the pair's three files, or the bare stem, names it), `--cached <pairs...>` checks the exact staged index bytes for hooks, and `hdsh pairing list` prints per-document state (missing, out-of-sync, ok) without failing. The corpus-wide form remains the authoritative check and runs in CI.

### Localized links

Every ordinary relative document link uses its source side's locale: the English side links to sibling `.md` paths, the Chinese side to `.zh.md` paths, and the gate reports a wrong-locale target with the expected URL. The language switcher is the one explicit cross-locale exception, and a README rendered outside GitHub may use the absolute URL the manifest's `public_blob_root` prefix configures to its exact counterpart so the switcher still resolves there. Targets are compared semantically: a link into the active bilingual corpus normalizes to the locale-independent pair anchor with its exact query or fragment suffix, so `.md` and `.zh.md` forms of one target compare equal in the structural signature, while targets outside the corpus and external URLs keep their authored bytes and are exempt. A missing counterpart in the corpus is a pair-completeness error, never a silent fallback. Link text is translated like any prose.

### Records compose under merge, fail-closed

`.gitattributes` routes `*.i18n.yaml` to the `hdsh-pairing` merge driver, registered worktree-locally by `hdsh worktree install` as `uv run --no-sync hdsh pairing merge-driver %O %A %B %P`, the CLI entry that absorbed the original shell launcher. The driver reads the ancestor, current, and other records, loads each record's two recorded owner blobs from the Git object database, and verifies each blob's content against its recorded hash. It runs Git's default text merge independently for the English and Chinese owners; if either owner has content conflicts, or the merged documents lose a required switcher, violate link locales, or diverge structurally, the driver fails and leaves the ordinary conflict in place. On success it stores the merged owners as blobs, pins them under the snapshot ref namespace, writes the composed record, and exits 0 so Git resolves the path. On composition failure the entry writes an ordinary text conflict into the record, prints the recovery pointer, and exits non-zero so Git keeps the index stages unresolved; when the runtime itself is unsynced the driver command fails and Git stops the merge with a driver error (`--probe` reports availability). An unverified clean text merge never counts as a resolved pairing record.

`hdsh pairing merge --resolve` applies the same fail-closed operation after a merge has already stopped: it resolves every mechanically composable sidecar conflict, stages the records as one batch, proves the staged owner merges match the composed ones and the worktree bytes are unstaged-clean, refuses to overwrite edited conflict content, and exits unsuccessfully listing anything that still needs manual work.

### Counterpart updates are minimal and happen in the editing turn

Editing either side obligates the same PR to bring the counterpart along, and the update is a minimal diff against the counterpart's last-confirmed state — never a whole-document re-translation, which discards reviewed phrasing, drifts established terminology, and costs the most. Routine translation is one shot and one pass by the active agent: load the [terminology table](../../../../docs/i18n/terminology.md), translate only the changed content, move a terminology first-occurrence annotation when the true first occurrence crosses the edit boundary, preserve reviewed counterpart prose outside the change, and re-record the pair. New pairs, whole-document translations, and difficult reconciliations are the escalation path, chosen explicitly rather than inferred from change size. Human review still owns semantic translation quality.

## Industry precedent

Paired sibling files with locale suffixes are the dominant convention among Chinese big-tech repositories (ant-design's `index.zh-CN.md`/`index.en-US.md`, arco-design's `README.zh-CN.md` with a top-of-file switcher, Apache ShardingSphere's `.cn.md`/`.en.md` pairs), but none of them enforce pairing or consistency in CI — the convention holds by review alone. Consistency automation exists elsewhere: MDN's `l10n.sourceCommit` front-matter fingerprint, Vue's Ryu-Cho upstream-commit watcher, Kubernetes' localization drift scripts, and Microsoft's source-hash-driven co-op-translator. This design combines the two — the Chinese-ecosystem file layout with a hash-pair gate — and runs the update as agent work in the same PR instead of a bot service.

## Alternatives considered

**English as the canonical source with a fingerprint inside the translation.** `.zh.md` files would carry an HTML comment recording the English source's blob hash, and translation would flow one way. Rejected: Chinese-first authoring with equal authority cannot be expressed by a one-directional canonical model; the sidecar covering both sides keeps the blob-hash mechanics and drops the direction.

**Locale directories (`docs/en/` plus `docs/zh/`).** Rejected: there is no docs-site framework to map locales to routes, moving every English file would churn every cross-reference, and link checks would need path-mapping logic instead of working unchanged.

**A separate translation repository.** Right for a docs product with independent release trains, overkill for a governance repository's own documentation, and it puts the translation outside the reach of this repository's gates.

**Interleaved bilingual files.** Doubles every diff, breaks the one-line-per-paragraph convention's diff ergonomics, and makes partial inconsistency invisible.

**Commit-hash records.** A same-PR edit has no commit hash yet, so such a record cannot express "consistent as of the state this PR introduces", and verifying it requires git history instead of file content.

**Comparing git timestamps of the pair.** Formatting-only edits would false-positive and a counterpart committed after an unrelated edit would false-negative; content identity is the only signal that means what the gate claims.

**Identical links on both sides.** Readers of each locale would be dropped into the other locale's documents, and every cross-reference would look identical rather than localized.

**Locale chosen per reader at render time.** There is no render step between this repository and GitHub's Markdown view; links are static text, so the locale must be baked into the path.

**Rewriting links in a preprocessing pass.** Sources must be correct as authored; a fix-up pass would make the checked-in bytes differ from what reviewers read and what the gate verifies.

**A union or theirs merge for records.** The resulting record would name one side's blobs while the tree carries merged documents; the gate would then reject every two-sided edit as out of sync.

**Regenerating records at merge time from the merged documents.** A generated record silently confirms a merge the driver never validated; a record means "a human confirmed these exact contents", which a merger cannot confer.

**Storing records outside Git.** The record must merge with the same branch mechanics as the documents it describes; a side channel loses atomicity and history.

**Whole-document re-translation as the update path.** Preservation collapses because reviewed phrasing is discarded, terminology drifts, and it is the most expensive path; the minimal-update rule stands.

**Per-paragraph translation-memory records in the sidecar.** Paragraph boundaries may legitimately differ across a pair, either side can be authored first, and segment records bloat and conflict in merges; whole-file hashes plus on-demand comparison recover the alignment when it is trustworthy.

**An automatically invoked translation skill for routine edits.** Another automatic skill adds discovery context and an invocation boundary around a task the active agent completes directly from the terminology table and standing instructions, and size-based inference of when to escalate is a hidden policy.

## Consequences

- Editing either side of a paired document obligates the same PR to update the counterpart and re-record the pair; CI, not reviewer memory, carries the invariant, and the cost of a small edit stays proportional to the edit.
- Every pair adds a third, machine-written file to the tree; in exchange, "who confirmed these consistent, and when" is answerable from git blame on the yaml, and the recorded hashes double as recovery pointers so repairing a drifted pair is a minimal diff against the edited side.
- When the two sides disagree, no mechanical rule picks a winner — the PR review does. That is the price of equal authority, accepted deliberately because a canonical language forbids Chinese-first authoring.
- The exclusions-only manifest makes every current and future in-scope document mandatory through the same path; creating a new in-corpus document requires naming its pair up front, because a link to an unpaired document fails the gate instead of silently crossing locales.
- Following any link keeps the reader in their locale whenever a counterpart exists; the corpus predicate, link resolution, and structural signature must move together when the corpus scope changes.
- Two-branch parallel edits to the same pair merge without manual sidecar work whenever the documents themselves merge cleanly; any doubt — runtime unavailable, owners conflict, structure diverges — leaves a normal Git conflict with the same recovery path as a driverless merge, and the composed record is only as sound as the text merges it composes.
- Gate passage means the pair's consistency is confirmed on the current content, not that the confirmation is correct: the check reads hashes and Markdown structure and cannot judge whether the two sides say the same thing; accuracy, terminology, and fluency remain review responsibilities.
