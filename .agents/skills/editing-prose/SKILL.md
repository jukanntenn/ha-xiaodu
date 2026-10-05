---
name: editing-prose
description: Use when writing, reviewing, restoring, trimming, or auditing prose in this repository, including deciding where documentation or comments are required across Markdown, docstrings, code and test comments, diagnostics, and CLI strings.
---

# Prose Standard

Write enough to preserve the contract, then remove reasoning transcripts, repetition, and decoration. A contract is an obligation, invariant, precondition, postcondition, or compatibility promise that a caller, callee, implementer, producer, or consumer relies on. This skill owns editorial judgment and required prose coverage; use [documenting](../documenting/SKILL.md) for placement, budgets, bilingual pairs, and documentation gates, and [trimming-cot-leakage](../trimming-cot-leakage/SKILL.md) for hunting and fixing reasoning-transcript leakage. It is guidance, not a script.

Treat `contract`, `boundary`, `gate`, and `vocabulary` as terms to check before use, not banned words. First ask whether the exact rule, API, field set, validation, timing point, or failure states the fact better. Keep a term when it names the exact technical subject, including caller/callee contracts and security/process boundaries.

Comments describe non-obvious contracts or rationale that code cannot express; they do not restate what code already implies.

## Inputs and exclusions

Require an explicit `scope`. If it is missing, report the required input and stop; do not infer a repository-wide scope or begin an interview.

Accept `mode: automatic | interactive`; default to `automatic`. Enter interactive mode only when the user explicitly requests questions or calibration.

`mode` controls questions, not write authority. Review and audit tasks report findings without editing; explicitly requested write, fix, or trim tasks apply clear changes.

Always exclude dependency, cache, build-output, and virtual-environment trees from discovery, review, and edits, even when the requested scope is the whole repository. Also exclude `.agents/rfcs/archived/` from prose review and edits: archived RFCs are frozen snapshots; inspect an exact target only to understand a historical inbound citation, never to modernize its prose or outbound links.

Treat generated regions (delimited by `<!-- BEGIN GENERATED ... -->` markers) and fixtures as derivative. Trace every consumer before editing: edit the owning source or generator first, then regenerate every derivative. Bilingual pairs have no permanent owner: either language may be the authored side for an update. Follow the [routine path](../../../docs/AGENTS.md#writing-rules), update the counterpart minimally, and re-record the pair.

## Preserve the complete proposition

Before editing, identify every proposition in the passage. Preserve each relevant:

- actor and action;
- condition, timing, and ordering;
- modality such as must, may, or never;
- negative guarantee and exception;
- ownership, side effect, failure mode, and consequence.

Remove adjectives, repetition, and narration only when every factual clause survives and the result is clearer. A smaller word count alone is not an improvement.

Keep a complete local contract at the point of use: behavior, failure, ownership, and consequence that a caller or maintainer needs there. Aggressively link to the owning document for architecture, rationale, algorithms, history, or extended examples. One explanation has one home; essential contract facts may repeat locally.

Keep non-obvious rationale when omitting it could plausibly cause misuse or an incorrect simplification. Otherwise state the consequence and link the rationale home.

## Required coverage by prose location

This is not a one-way shortening pass. Add or restore prose when code, types, and structure do not communicate a required contract below. Do not add a comment when those facts are already obvious locally.

- **Public docstrings:** document caller-visible return distinctions, raised exceptions, side effects, ownership, timing, and durability.
- **Internal comments:** orient non-local structure and obviously complicated local structure, including invariants, race ordering, ownership, security boundaries, and surprising failure behavior. Delete control-flow narration and code restatement.
- **Module comments:** state the module's role, dependencies, responsibilities, and non-obvious architecture choices; link architecture choices to their owning explanation.
- **Tests:** explain only non-obvious test design—why a fixture, assertion, platform accommodation, real entry path, or indirect observation is necessary. Delete walkthroughs and inventories.
- **Cookbooks:** include prerequisites, required actions, the real entry path, observable verification, and concise warnings.
- **Contract references:** include the consumer contract: configuration, semantics, failures, limitations, and extension points. Keep durable gaps and maintainer traps, not ordinary cleanup inventories.
- **RFCs:** retain unique rationale, mechanisms, alternatives, consequences, shipped verification evidence, and named coverage gaps. Implemented RFCs state shipped reality in the present tense; remove planning checklists, not evidence of what pins the decision.
- **Skills and agent instructions:** state behavioral guardrails and explicit scope limitations such as "guidance, not a script/checklist". Keep the workflow concise and link its source of truth.
- **Examples and configuration comments:** explain access limits, non-obvious wiring or load order, security stance, replay behavior, exceptions, and likely misuse. Do not narrate entries that the configuration already shows.
- **Diagnostics and CLI strings:** treat wording as behavior. Name the failing subject or path, violated rule, and correction when it is non-obvious. Remove internal execution narration.
- **Terminology and translation prose:** follow [terminology.md](../../../docs/i18n/terminology.md) and [translation-rules.md](../../../docs/i18n/translation-rules.md); wording decisions made in review land in the terminology table, not only in one file.

Preserve searchable mechanism names and meaningful modal, temporal, or negative emphasis. Normalize decorative emphasis only.

## Workflow

1. Confirm the scope, mode, current branch or PR base, and applicable `AGENTS.md` files. Do not inspect unrelated branches.
2. Read [the documentation standard](../../../docs/AGENTS.md) and the owning code or document before judging a passage. For calibration or unfamiliar cases, read [the distilled examples](references/examples.md).
3. Inspect the requested scope, not only the largest files. Use searches and word counts to find candidates, then judge passages semantically.
4. Classify each candidate as keep, add, trim, restore, restructure, or defer. Apply clear changes only when the task authorizes edits; do not manufacture edits to satisfy a deletion target.
5. Update the owner before derivative artifacts. Re-check analogous passages after learning a new rule.
6. Run the narrow relevant checks, the documentation gates, `git diff --check`, and focused tests for diagnostics and CLI strings.
7. Report the inspected scope, clear changes, deliberate keeps, deferred cases, and checks actually run.

## Borderline decisions

A case is borderline only when at least two versions satisfy the complete-proposition rule but trade accepted principles, and this skill does not already resolve the tradeoff. A rewrite with one proposition-preserving answer is not borderline.

In automatic mode, apply clear edits when authorized and report genuine borderline cases without asking questions. Do not weaken a proposition to make progress.

In interactive mode, group analogous passages under the governing principle. Present two or three viable versions, recommend one, and state the factual or structural difference. Do not offer inferior distractors. Use the user's requested channel; when calibrating a PR through inline comments, place the recommended provisional version in the diff and attach the alternatives to that exact line.

After the user decides, distill the principle and versions into [the examples](references/examples.md), without PR history or reviewer narration, and apply the learned rule to every analogous passage in scope.
