# RFC: Briefed minimal translation updates

Status: implemented

English | [中文](2026-09-07-briefed-minimal-translation-updates.zh.md)

## Problem

The pairing contract obligates the same PR to bring the counterpart along, but two tempting defaults waste that obligation's budget. Re-translating the whole document discards the reviewed phrasing of everything the edit did not touch and re-opens settled terminology; loading the whole guidance corpus for a two-line edit taxes exactly the behavior the contract wants to keep cheap. Routine agent work therefore translates the changed content directly in one terminology-guided pass — but the heavier reconciliation cases (whole-document translation, both-sides-drifted pairs, subagent delegation) needed a working set that carries the diff, the three-way context, the touched terminology rows, and the binding rules in one place instead of implying them.

## Decision

`hdsh pairing brief [--apply] [<pair>...]` renders that working set on demand and never runs in hooks or CI:

- Each out-of-sync side is mapped at the narrowest safely aligned granularity: a code-fence-only splice, changed Markdown units (outermost block nodes; the container path is part of the alignment kind), whole heading sections, then the whole document. Alignment compares language-neutral kinds — heading depth, node type, container membership — never heading text.
- A change confined to byte-identical fences is mechanical: `--apply` splices the edited fences into the counterpart and structure-validates the result (the pairing signature) before writing. No translation judgment is involved.
- Each briefing bundles, per changed span: last-confirmed source, current source, and current counterpart text with counterpart line numbers; plus the authored-side diff, the terminology rows whose source-language term occurs in the changed text, first-occurrence movement notes (the 首次出现 gloss moves with the document-wide first occurrence, so an edit that moves it obligates both the old and new spans), and a direction-specific rules digest.
- Both-sides-drifted pairs always brief as whole-document work: no side is a trustworthy mapping anchor.
- Named pairs fail loud when in sync, incomplete, or out of scope; with no arguments the tool briefs every out-of-sync pair. Recording stays with `hdsh pairing record`.

The extended workflow that consumes briefings is [`translating-docs`](../../../skills/translating-docs/SKILL.md), user-invocable only; routine updates keep the direct one-pass path in [docs/AGENTS.md](../../../../docs/AGENTS.md). No automated translation pipeline exists in this repository, and no machine-consumed prompt template ships in the corpus.

## Alternatives considered

**Always re-translate the counterpart.** Rejects reviewed phrasing and re-opens terminology on every edit; the recorded hashes exist precisely to make the minimal diff recoverable.

**A standing briefing file per pair in the tree.** It would rot between edits and add a fourth artifact to the pair's merge surface; a briefing is a rendering of recorded state, derivable on demand.

**Deriving the change from git history instead of the consistency record.** The record's blob hashes already name the exact last-confirmed state without history lookups, and they cover never-committed working-tree bytes because recording stores snapshots first.

**Hook- or CI-driven briefings.** The briefing exists to make an explicitly requested heavier workflow cheap; running it automatically would re-create the corpus-loading tax the design removes.

**Shipping a machine-consumed prompt template.** Its body changes pipeline behavior verbatim and this repository runs no such pipeline; a paired template would be dead weight behind an extra exclusion.

## Consequences

- The direct one-pass rule stays the default; briefings are an explicitly invocable accelerator, and the skills corpus gains `translating-docs` with `disable-model-invocation: true`.
- Brief quality depends on the recorded state: a malformed or missing record fails loud rather than guessing a baseline.
- Alignment is conservative by construction — any structural divergence between the last-confirmed source, current source, and current counterpart escalates to a wider scope instead of mis-mapping spans; changes invisible to both units and sections (for example line-ending drift) escalate to the whole document.
- The span grammar lives in one module alongside the pairing signature's parser, so unit kinds and the gate's structural comparison cannot drift apart silently; tests pin the mapping, the mechanical splice, first-occurrence tracking, and the CLI surfaces at full branch coverage.
