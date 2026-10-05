# RFC: Document corpus gates: hard wrap, cross-links, and word budgets

Status: implemented

English | [中文](2026-09-07-document-corpus-gates.zh.md)

## Problem

The documentation standard ([docs/AGENTS.md](../../../../docs/AGENTS.md)) states three invariants that review alone does not hold. Prose is one physical line per paragraph, because hard-wrapped prose hides which words a change touched — a one-word edit reflows every wrapped line — and makes bilingual pairs noisier to compare; verified by eyeball, the rule drifts. Documents cross-reference each other by relative path — README to the pairing contract, RFC to RFC, RFCs into skills — and nothing verified that those targets, or the `#fragment` anchors onto them, existed; a reworded heading or relocated contract fails silently until a reader clicks. And standing documents accrete — repeated rules, retold stories, restated maps — because a prose rule with no mechanical backstop demonstrably does not hold, so the standard's "each fact has one home" rule needs an enforcement frontier. HDSH packages the gates so that consuming repositories, this one included, get them as configuration rather than convention.

## Decision

Three verify-only prek hooks share one package, one configuration file ([`.hdsh/docs.manifest.json`](../../../../.hdsh/docs.manifest.json)), and one stance: the corpus is configuration, not code. Include and exclude globs and ceilings come from the consuming repository's manifest and are validated at load — empty patterns, absolute paths, `..` segments, and non-positive or non-integer ceilings are rejected before any checking — symlinked files are deduped by real path, and the frozen `.agents/rfcs/archived/` tree is excluded by glob. Each gate reports and never rewrites.

### `hdsh docs wrap` (hook `hdsh-docs-wrap`)

Each file in the `markdownWrap` corpus is parsed with markdown-it-py (CommonMark plus the GFM table extension), and any paragraph token — including paragraphs inside lists and blockquotes — whose line map spans more than one source line is reported with its file, line, and first-line snippet. Fenced code, tables, headings, and list structure keep their formatting and never violate. YAML frontmatter and `:::` container delimiters are masked before parsing so doc-site sources do not false-positive; masking blanks lines in place, so reports still name real lines.

### `hdsh docs links` (hook `hdsh-docs-links`)

Links, images, and reference definitions are collected from the markdown-it-py token stream of each file in the `markdownLinks` corpus: every definition — shadowed duplicates included — arrives as a token at its authored line, and an inline destination reports the line it was written on rather than its block's first line. Destinations keep their authored text (the parser's URL normalizer is the identity), so diagnostics quote what the author wrote. A relative target must exist, and a `#fragment` onto a Markdown target — same-file anchors included — must name a real heading slug or an explicit `<a id>` in real HTML flow; anchors inside code samples and commented-out HTML register nothing. Scheme URLs, protocol-relative and root-absolute targets, and fragments onto non-Markdown targets (`file.py#L10`) stay out of scope. Slugs follow GitHub's algorithm computed from rendered heading text, so links, inline code, and emphasis inside a heading slug as rendered; underscores survive, CJK headings keep their characters, repeated slugs get the occupied-set `-1`, `-2` suffixes, and matching is exact-case. Chinese pair sides follow the corpus convention of explicit `<a id>` anchors plus English fragments. Percent-encoding is decoded the way a renderer resolves targets, and a malformed escape stays raw so the link reports broken instead of crashing the gate. Anchor sets are computed lazily and cached per target, so links into any existing file validate without making that file a source; the archived tree is excluded from scanning but remains a valid link target.

### `hdsh docs budgets` (hook `hdsh-docs-budgets`)

Ceilings are `wc -w` counts (whitespace-delimited tokens over the whole file) listed per path in the `docBudgets` section. A budgeted file that is missing fails the gate, so a rename cannot silently orphan its budget; `--list` reports current usage without failing. Only the accretion-prone standing documents are budgeted — the root `AGENTS.md`, `docs/AGENTS.md`, the README pair, and the architecture and development pairs; references, RFCs, and skills are unbudgeted because length is legitimate there when every row is a fact, and review governs them. Ceilings are an enforcement frontier that ratchets: they keep at least five percent headroom, ratchet down whenever a document reaches its target, and raising one requires explicit justification in the PR.

## Verification

`tests/docs/` pins the wrap paragraph semantics (top-level, list, and blockquote prose judged; fences and tables never), the frontmatter and `:::` masking branches, snippet truncation, corpus ordering with excludes and symlink dedup, and the manifest validation matrix; rendered-text slugging (backticks, punctuation, a linked heading, kept underscores, CJK), occupied-set repeat suffixes, explicit anchors ignored inside fences, inline code, and comments, same-file and cross-file fragment resolution, case-variant and cross-file misses, a missing target reported as a target rather than an anchor, shadowed duplicate definitions checked at their own lines, and destinations keeping their authored text and reporting their own line; and `wc -w` counting, the ok/OVER/MISS rows, the missing-file failure, `--list`, argument validation, and the load-time ceiling matrix. pytest runs under the 100% branch-coverage gate, and the repository's own corpus passes all three gates.

## Alternatives considered

**A regex line scan instead of the parser.** Paragraph shape is a parsed property: lists, blockquotes, and lazy continuation defeat line heuristics, and markdown-it-py is already a runtime dependency of the pairing gate.

**A formatter that rewraps on commit.** Verify, don't generate: a reflowing hook rewrites every paragraph a change touches and manufactures diff noise instead of preventing it.

**Hardcoded corpus patterns.** A gate consumed by other repositories cannot ship a consuming repository's file list; globs belong to the consuming repository's manifest.

**File-level link checking only.** Fragments rot anyway, because heading rewrites happen in PRs that never look at inbound links; the fragment check is the half that catches the decay.

**Chinese-heading slugs for zh sides.** GitHub slugs CJK headings, but explicit anchors plus English fragments also survive renderers that strip non-ASCII; a second convention would split the corpus.

**Reusing the pairing gate's link machinery.** `hdsh.pairing.links` compares link targets semantically across a locale pair — it assumes targets exist and answers a different question. Existence and anchor validity get their own collector.

**Guidance and review without a budget gate.** Accretion happens under exactly those conditions; invariants worth keeping are worth encoding.

**A broad budget over every document.** A blanket ceiling punishes the right kind of long document — a reference where every row is a fact — and breeds per-file override churn that trains contributors to rubber-stamp raises.

**Check-time ceiling validation.** A manifest entry of zero is a configuration defect fully detectable at load; reporting it as a check-time row lets a broken manifest hide behind a green-ish run, which the repository's misconfiguration-fails-loud rule forbids.

## Consequences

- The one-line rule is mechanical over the configured corpus, so diffs show exactly the words that changed and the pairing gate's structural comparison stays legible; pre-commit runs the gates when Markdown is staged and CI runs them always.
- Renaming a heading or moving a document fails the gate wherever a Markdown link cites it, instead of stranding readers; authors repair inbound links in the same change, exactly as they already must for the pairing gate's structural signature. Same-file anchors are no blind spot, so a zh page that keeps an English fragment must expose the matching explicit anchor.
- Adding to a budgeted document requires displacement — relocate the addition to its owning document with a pointer, or condense existing prose to pay for it; growth without pruning fails the gate. Word count is a crude proxy, accepted deliberately: it cannot judge quality, but it forces the relocation decision at the moment content is added, when the author has the context to place it correctly.
