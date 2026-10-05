---
name: archiving-rfcs
description: Use when adding, auditing, pruning, archiving, restoring, or reviewing RFCs in this repository; checks every new RFC for superseded active records, classifies implemented RFCs by future decision value, deletes rejected RFCs that no longer prevent a tempting mistake, and applies the frozen archived/{class} triplet and manifest seal rules.
---

# Archive RFCs

Reduce the active decision corpus without erasing history that can still guide work. Judge every RFC semantically; word count and age are discovery aids, never archive criteria.

## Read the contracts

Read [the RFC rules](../../rfcs/README.md), [the archive instructions](../../rfcs/archived/AGENTS.md), and the applicable active lifecycle instructions before classifying. Use current code, configuration, newer RFCs, and inbound links to establish whether a rationale still owns or constrains anything.

## Check supersession when adding an RFC

Every new RFC triggers a scoped audit of active RFCs covering the same decision, mechanism, or rejected alternative. Classify each full or partial supersession while writing the new RFC: archive qualifying implemented triplets in the same PR, retain and cross-link partial supersessions or independently useful rationale, reject obsolete proposals, and delete rejected RFCs that no longer prevent a plausible mistake. Apply the consolidation rule from the [RFC rules](../../rfcs/README.md) when the new owner absorbs every unique proposition; do not defer a known match to a later corpus audit.

## Classify by future value

Apply these lifecycle-specific outcomes:

- **Implemented — keep active:** retain an RFC when its rationale, alternatives, negative guarantees, durable-format semantics, ownership boundary, security rule, or reintroduction condition is likely to guide a future change. Length does not matter.
- **Implemented — archive:** archive an RFC when the shipped decision is complete and its body is unlikely to guide future work, such as a narrow closed fix, a superseded implementation detail, or process history whose current authority is obvious elsewhere.
- **Proposed — never archive:** keep a live proposal active; if it is no longer worth pursuing, reject it with an honest reason and satisfy the rejected lifecycle format.
- **Rejected — keep only as a guardrail:** retain a rejection only when the losing proposal remains a tempting, meaningful mistake and the RFC explains why it loses.
- **Rejected — delete:** delete the whole triplet when the rejected idea is obsolete, superseded, no longer plausible, or unlikely to prevent re-litigation. Repair or delete inbound links.

Do not archive toward a quota. Inspect every RFC in scope, classify analogous groups under one principle, use best judgment for close cases, and record genuinely borderline decisions for the handoff.

## Calibrated examples

These examples set the bar; the approximate sizes demonstrate that size is not the test.

Archive implemented RFCs such as: a one-off adapter workaround of roughly 500 words whose mechanism is closed and has no future design leverage; a minor bug fix of roughly 300 words whose current behavior is obvious from the code; completed process history of roughly 900 words whose current authority lives in the document that owns the rule now.

Keep implemented RFCs such as: the bilingual pairing contract of roughly 1000 words, a foundational authority; a negative guarantee while the design temptation it prevents remains plausible; any RFC that states a reintroduction condition, until that condition resolves.

For rejected RFCs: keep one whose losing proposal remains a tempting, meaningful mistake; delete one whose premise a later decision has already resolved.

## Archive one implemented triplet

1. Move the complete `<rfc>.md`, `<rfc>.zh.md`, and `<rfc>.i18n.yaml` triplet from `implemented/<class>/` to `archived/<class>/`; `implemented` is deliberately absent from the archive path. Do not translate, reformat, update facts, or repair links inside the RFC.
2. Make no body edits. Insert only `Archived: YYYY-MM-DD` immediately below `Status: implemented` in both language files, using the archival date and the same value on both sides.
3. While the triplet still lives under `implemented/`, re-record the sidecar for the two metadata-only edits with `hdsh pairing record .agents/rfcs/implemented/<class>/<rfc>.md` — the pairing corpus excludes the archived tree, so the record must happen before the move.
4. Search for inbound links from active prose. Redirect them to current authority, retarget them to the archived path only when the historical snapshot is intentionally cited, or delete them. Never verify or repair links out of the archived RFC.
5. Run `hdsh rfc seal`. Its append-only mode first proves every existing seal still matches, then adds only the new triplet hashes. Run `hdsh rfc archive` afterward.

After the triplet is sealed, never edit, move, translate, reformat, or delete it. Archived RFCs remain valid inbound-link targets but are historical snapshots, not authority for current behavior.

## Validate and report

Run `hdsh rfc archive` and the focused archive tests; select any additional evidence through [pushing](../pushing/SKILL.md).

<!-- hdsh:slot archive-tests -->
This repository ships no local archive tests; the host-installed `hdsh rfc archive` gate is the whole check for `.agents/rfcs/archived/`.
<!-- /hdsh:slot -->

Report active implemented RFCs kept, implemented RFCs archived, rejected RFCs kept and deleted, proposed RFCs rejected if any, and every genuinely borderline case with its rationale and chosen outcome. Do not claim archived outbound links are valid: the archive gate intentionally never checks them.
