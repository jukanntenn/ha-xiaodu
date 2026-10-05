---
name: finding-simplifications
description: 'Use when working in this repository to find non-obvious simplification candidates, remove redundant comments or implementation-heavy documentation, write proposed RFCs or inline TODO/FIXME/XXX notes, audit or coalesce superseded RFCs, or fold worthwhile simplification ideas from another PR; especially for dead, duplicated, speculative, over-built, added-then-removed, or hand-rolled-where-a-dependency-exists surfaces.'
---

# Finding Simplifications

This skill helps turn a broad "find things to simplify" request into evidence-backed RFCs that remove or collapse existing harness surface area. It is guidance, not a checklist: follow the code, keep judgment active, and prefer a few well-proven candidates over a pile of thin guesses.

## Start With Repo Context

- Read `AGENTS.md`, especially the conventions, plus [docs/architecture.md](../../../docs/architecture.md) and [docs/development.md](../../../docs/development.md).
- Skim [docs/architecture.md](../../../docs/architecture.md) before judging anything in the production source tree; simplifications that fight the domain map need extra evidence.
- Use the RFC tree and its [rules](../../rfcs/README.md) to understand intentional architecture: the implemented records own the settled seams.
- Treat decisions recorded in implemented RFCs as intentional by default. Do not propose deleting a recorded seam as "low effort" unless the user explicitly overrides that constraint. Removing an unused function or option inside a protected design can still be valid if it does not collapse the protected design.

## What Counts As A Strong Candidate

A strong simplification removes, folds, or demotes something real and has clear evidence that the current design costs more than it buys:

- A public function, CLI option, config knob, hook, helper, or test artifact has no production consumer.
- Tests or docs are the only consumers, and the behavior they pin is not load-bearing.
- Two representations mirror the same fact.
- A seam has methods every implementation must support but no consumer uses.
- A feature implements speculative product generality: a design with no product owner.
- An invariant, rollback path, set of expected outputs, or special-case test exists only to protect an unused API.
- Hand-rolled code reimplements what the Python standard library or a well-maintained PyPI package already provides, and the swap would delete the implementation plus its dedicated tests.
- The simplified behavior may differ slightly, but the new behavior is still reasonable and easier to explain.

Thin candidates are not enough for an RFC: deleting one typo, removing an intentionally documented option, or flagging "this looks complex" without call-site proof.

## Survey Broadly

Use parallel subagents when the user asks for breadth or many candidates. Give each agent a domain and require evidence, not guesses. Useful domains:

- Pairing: corpus discovery, structure signatures, records, the merge driver.
- RFC gates: format verification, the sealed archive.
- Docs gates: wrap, links, budgets, the corpus manifest.
- Scope and worktree: change-scope analysis, hook installation, config ownership.
- Policy and CLI: label rules, argument parsing, diagnostics.

If subagents are unavailable, simulate the same breadth yourself. Do not let the first good candidate stop the survey.

Start with the largest production-code deltas. A broad simplification audit that stops after obvious unused symbols can miss the files where duplicated lifecycle or defensive machinery carries most of the cost.

## Simplify Prose With The Code

Treat comments and documentation as maintained surface area. Apply [editing-prose](../editing-prose/SKILL.md) when a survey includes prose.

- Delete comments that restate code or explain behavior owned elsewhere; keep required local contracts.
- Keep docs at their owning level; omit implementation details and rare cases unless they change a maintained contract.

## Audit Trust And Lifecycle Boundaries

For every defensive copy, freeze, validator, and callback capture, name where the value came from and who owns it next. Same-process typed calls ordinarily borrow readonly values; parsers, config loaders, subprocess output, file readers, and wire decoders own or validate their data. Tests built around hostile getters, fake typed objects, callback replacement, or mutation after a same-process handoff are evidence of a potentially speculative contract, not automatic justification for keeping it.

## Hand-Rolled Code Versus A Dependency

Introducing a dependency is a valid simplification move, not a policy exception. When surveying, ask of protocol parsers, retry/backoff loops, glob matchers, diff engines, and similar infrastructure: does the Python standard library or a well-maintained PyPI package already do this?

Prove a dependency-swap candidate like any other, plus:

- Read the hand-rolled implementation and name the exact surface the package covers; residual semantics the package does not cover count against the swap and stay in the RFC.
- Check the package's health honestly (maintenance, adoption, transitive footprint) and prefer standard-library modules when they cover the need.
- Check the RFC tree first: recorded seams are settled — a swap that collapses one needs to beat the recorded rationale, not just the general argument.
- Weigh net deletion: implementation plus dedicated tests plus docs, minus the glue that remains. A wrapper that relocates the same complexity is not a win.

## Prove Or Reject Each Candidate

For every symbol or behavior, classify consumers before writing:

- Production corpus:

<!-- hdsh:slot production-corpus -->
`custom_components/xiaodu/` (`api/`, `bemfa/`, platform files, `coordinator.py`, `entity.py`, `config_flow.py`, `const.py`), plus `manifest.json`, `strings.json`, `translations/`, `hacs.json`, and `prek.toml` — anything HA loads at runtime or CI executes as a gate.
<!-- /hdsh:slot -->
- Non-production corpus: tests, README/docs, RFCs, fixtures, and comments.
- Ambiguous corpus: documentation examples and snippets that may double as product paths. Inspect usage before classifying.

Use `rg` first. Good searches include the exact symbol, command name, option spelling, config key, method name with both `.name(` and `name(`, and any diagnostic strings. Then read the call sites, public interfaces, tests, docs, and the hook and merge-driver registrations.

Reject or downgrade a candidate when:

- A production caller exists and the simplification would be a feature decision rather than a cleanup.
- The API is explicitly justified by an implemented RFC or a hard-won defensive pattern, and the new evidence does not beat that reason.
- The removal would force unrelated churn without actually reducing the public API or required behavior.
- The idea is correct but tiny. Add a targeted TODO/FIXME/XXX instead, using the urgency semantics in the root `AGENTS.md`.

## Coalesce Superseded RFCs

Audit the RFC tree when the user asks to reduce or coalesce it, or when the simplification being implemented makes an owning RFC obsolete. Do not expand every code-simplification survey into a repository-wide RFC audit.

Use [archiving-rfcs](../archiving-rfcs/SKILL.md) for retention judgment and archive mechanics. Low-future-value implemented RFCs move as frozen triplets to `archived/{class}`; proposed RFCs are never archived; rejected RFCs that no longer prevent a tempting mistake are deleted. Do not edit an archived RFC while simplifying current prose or code.

Follow the consolidation rule in the [RFC rules](../../rfcs/README.md); do not duplicate or weaken it here. For each candidate chain:

1. Identify the current owner from shipped code, configuration, docs, newer RFCs, and inbound links; dates and titles are discovery hints, not proof.
2. Classify the old RFC as fully or partially superseded. Any surviving behavior, current contract, durable format, compatibility obligation, or independently current rejected alternative makes it partial. Rationale that can be transferred to the current owner does not by itself make supersession partial.
3. For full supersession, move every unique rationale, alternative, consequence, shipped verification evidence, and named coverage gap into the current owner. An inventory that only describes deleted implementation mechanics is not one of those decision facts.
4. Repair every inbound link, then delete the English RFC, Chinese counterpart, and consistency record together.
5. Search exact filenames, symbols, config keys, and command names after the edit. Keep partial supersessions cross-linked and current.

An added-then-removed feature is a common full-supersession case; the RFC rules own when a feature-addition RFC may be consolidated into its removal RFC. Reject consolidation when the removal is only one transport, default, implementation, or presentation of a feature; when persisted data or compatibility handling survives; or when the removal RFC does not yet carry enough rationale to prevent accidental reintroduction.

## Write The RFC

Create one triplet per durable proposal under `.agents/rfcs/proposed/simplification/yyyy-mm-dd-topic.md`, following the lifecycle and classification rules in [the RFC rules](../../rfcs/README.md). Keep prose paragraphs on one physical line and use relative Markdown links.

Prefer this structure, adjusting when the idea needs it:

- `# RFC: <action-oriented title>`
- `Status: proposed`
- `## Problem`: name the current API, cite the relevant files, and state the consumer evidence. Separate production callers from tests/docs.
- `## Proposal`: say exactly what to remove, fold, demote, or rehome. Include tests, docs, README, hook, and manifest cleanup when relevant.
- `## Alternatives considered`: make the strongest counterargument legible — what keeping the current design buys, and what the removal gives up.
- `## Acceptance criteria`: observable end state and gates.
- `## Risks`: public API changes, behavior changes, future product wants, and why the tradeoff is still reasonable.

Write the Chinese counterpart and record the pair in the same change. Be concrete enough that an implementing PR can follow the trail; avoid vague "simplify this module" RFCs. When a proposal overlaps an existing RFC, consolidate the useful details into the existing one rather than creating a duplicate.

## Inline TODO Notes

Use inline TODO/FIXME/XXX only for small, local cleanups that are clearly useful but not durable design decisions. Keep them short and actionable:

- Name the smell with a stable tag, e.g. `TODO(double-default)` or `XXX(unused-default)`.
- Explain why it is safe to revisit and what action would simplify it.
- Do not add TODOs for speculative complaints or for behavior that needs an RFC-level decision.

## When Folding Another PR Or Branch

Diff the sibling branch against `origin/main`, not against the current PR branch, so you see its independent contribution. For each item:

- Port non-overlapping RFCs or TODOs that meet the quality bar.
- Consolidate overlapping material into the existing RFC that owns the topic.
- Do not port duplicate or lower-confidence proposals just to preserve the count.
- Update the PR body so reviewers see the true candidate count and scope.
- Close the duplicate PR only when the user asked you to, or when you clearly own that housekeeping.

## Validation And PR Hygiene

For docs-only RFC work, run at least `hdsh rfc verify`, `hdsh pairing verify`, `hdsh docs wrap`, `hdsh docs links`, and `git diff --check`. For code comments or skill changes, also run the focused tests that cover the touched surface. Select any other evidence from the outgoing diff; the [pushing](../pushing/SKILL.md) workflow owns the pre-publish selection.

When opening or updating a PR, summarize:

- How many RFCs and inline notes were added, consolidated, retained as partial supersessions, or deleted.
- The main areas surveyed.
- What was intentionally excluded.
- Which checks passed.

For each consolidation group, name the old and current owners, state the evidence for full supersession, and explain why deletion is safe. If an added-then-removed scan finds no qualifying RFC, report that result and the representative partial cases retained.

Use a draft PR while the survey is still expanding; mark ready only when the candidate set, review responses, and validation are settled.
