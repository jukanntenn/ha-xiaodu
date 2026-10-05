---
name: documenting
description: Create, restructure, review, audit, or migrate this repository's Markdown documentation using audience-first hierarchy, bilingual line alignment, executed-operation fact-checking, and repository validation. Use for new or revised repository docs, docs-tree organization, documentation-quality audits and budgets, and bilingual documentation structure changes.
---

# Documentation

## Summary

The documentation standard: make every page searchable, newcomer-readable, and exact enough for agents and maintainers. Apply repository `AGENTS.md` files and the executed hdsh gates first, then this workflow for placement, progressive detail, line-aligned bilingual pages, and corpus audits. Preserve one owner per fact: source, tests, RFCs, guides, and skills each keep their own kind of truth.

## Workflow

Follow this sequence for each requested scope. Keep the common reader path brief, but do not delete failures, ownership, limitations, or other required contracts merely to reduce words.

1. Read the root and more-specific `AGENTS.md` files, [the documentation standard](../../../docs/AGENTS.md), the target page, its source or owning tests, and the bilingual record.
2. Classify the page by one primary job and reader: product overview, contributor tutorial, architecture overview, contract reference, cookbook guide, agent instruction, or decision record.
3. Place the page at its nearest owner. Use `docs/` for cross-domain learning, developer, and architecture material; use `docs/cookbook/` for step-by-step procedures; decisions go to `.agents/rfcs/`, workflows to `.agents/skills/`.
4. Define the reader's starting state, observable outcome, likely failure, recovery path, and next useful depth before writing details.
5. Write the content in the document standard's authoring order: locate, set permitted detail, classify tutorial or reference, order concepts, relocate descendant-owned detail, link instead of restating.
6. Update the bilingual counterpart in the same pass. Keep headings, lists, tables, code, links, and structure aligned per [the pairing contract](../../../docs/i18n/README.md).
7. Verify every claim against code, tests, gate output, or a current decision owner — and run the operations the page instructs, per the fact-check procedure below. Update the owner before any derivative artifact.
8. Run the focused checks: `hdsh pairing verify <pair>`, `hdsh docs wrap`, `hdsh docs links`, `hdsh docs budgets`; re-read the complete diff for correctness and then for brevity and repository fit.

## Fact-check procedure: test, do not assume

Documentation states how the product behaves today, and the only admissible evidence for an operation claim is having run it. This procedure is mandatory for every new document and every new paragraph that claims an operation, command, default, error, or platform difference.

1. **Run every claimed operation against the current checkout.** Execute each CLI command, config snippet, and manifest example exactly as the document will show it; write down only what you observed, including the exact output, warnings, and failure modes. If a claim depends on credentials or a network you do not have, say so and name the verification owner instead of asserting the behavior.
2. **Delete what you could not reproduce.** Never carry a command, field, default value, or behavior from memory, analogy, or a neighboring document. When a claim fails to reproduce, fix the claim — not the observation.
3. **Check old docs against latest main.** Before revising pre-existing pages, compare the section against `origin/main`; the pairing record recovers the last-confirmed text of either side with `git cat-file -p <hash>`. A stale statement on main is still wrong: correct it against the code, not against the old prose.
4. **Re-record the pair after every edit.** Each paired edit re-runs `hdsh pairing record <pair>` so the record tracks the confirmed pair.

## Voice rules

These rules decide what a section may say.

- **Openings say what the subject does.** The opening of a page or section describes what a reader or agent can DO with the subject — outcomes, when to choose it, main cost — never its role, type, or internal identity.
- **Explanations, never enumerations.** Prose covers the design concept and dataflow — enough to understand how the subject works — and links code or the owning reference for exact detail. No exhaustive inventories or restatement of what a table or gate output already shows.
- **Current state only.** No compatibility talk, migration talk, or history ("previously", "now", "no longer", renamed); the codebase and corpus as they are today are the only subject. Change stories belong in commits and RFCs.
- **Use controlled technical English.** Give each sentence an explicit actor and one main action when ambiguity can change behavior. Reuse one term per concept, prefer direct verbs, split stacked instructions and conditions, and preserve modality and exceptions. Do not force a shorter sentence when precision would fall.

## Quality criteria

Use these definitions in review. Each section opens with a short orienting paragraph before subsections or exhaustive detail.

- **Brief:** the common path contains only facts needed for its outcome; exhaustive truth remains one direct link away.
- **Intuitive:** prerequisites precede dependent concepts, one next action is obvious, and headings use terms readers search for.
- **Friendly:** readers can recognize success, understand risk before acting, recover from likely failure, and choose whether to continue deeper.
- **Accurate:** each durable claim has one owner and a verification path proportionate to its risk.
- **Agent-readable:** stable headings, terminology, ownership, and current-state prose support targeted retrieval without loading the corpus.
- **Newcomer-complete:** a professional engineer with no repository context can reconstruct the relevant architecture or feature through three to five linked pages.

## Audit the corpus

Read, do not re-summarize, the owning contracts: [docs/AGENTS.md](../../../docs/AGENTS.md) for hierarchy, forms, taxonomy, budgets, and the slop checklist; [.agents/rfcs/README.md](../../rfcs/README.md) for the RFC lifecycle; [docs/i18n/README.md](../../../docs/i18n/README.md) for the bilingual pairing rules; and the [root AGENTS.md](../../../AGENTS.md) for standing orders. Exclude `.agents/rfcs/archived/` from audits and edits — archived RFCs are frozen history.

Apply the standard's authoring order to every human-facing document in scope. Then check placement constraints: paired docs cost a counterpart update and a re-record on every edit; a move is atomic with every inbound link repaired in the same change.

After the structural pass, hunt the slop checklist with the cheapest probes first: use [trimming-cot-leakage](../trimming-cot-leakage/SKILL.md) for reasoning-transcript leakage, grep distinctive phrases to find duplicated rules, replace hand-written inventories with their authoritative owners, and remove migration plans and future-tense spec language from implemented RFCs. Measure outliers with `hdsh docs budgets --list` and a word-count scan; if removing prose changes a promised behavior rather than its explanation, propose the behavior change first (follow [finding-simplifications](../finding-simplifications/SKILL.md)). Keep every load-bearing rule, preferably as one to three lines plus a link to its rationale; do not create a new explanation merely to relocate disposable reasoning.

## Wordcount budgets

`hdsh docs budgets` compares standing documents against ceilings in [.hdsh/docs.manifest.json](../../../.hdsh/docs.manifest.json); a red gate follows the ordered relocate-condense-raise policy in [docs/AGENTS.md](../../../docs/AGENTS.md#wordcount-budgets). Ceilings are guardrails, not reduction targets: at or below target, retain at least 5% headroom; raise a ceiling only when the words need the space, and justify the manifest diff in the PR.

## Validation

Validate the affected contract, not merely Markdown syntax. A strong promise needs a focused valid fixture and an invalid fixture that proves the gate can fail.

- Bilingual pages: verify structure, terminology, link parity, and the consistency record through `hdsh pairing verify <pair>`.
- Tutorials: exercise the documented entry path or name an explicit manual verification owner.
- Corpus changes: run `hdsh docs wrap`, `hdsh docs links`, and `hdsh docs budgets` over the whole tree before finishing.

## Dev Note

None.
