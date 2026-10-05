# AGENTS.md — Implemented RFCs

These RFCs describe shipped decisions. Follow the [root instructions](../../../AGENTS.md), [documentation standard](../../../docs/AGENTS.md), and [RFC format](../README.md#the-file-format); `hdsh rfc verify` gates the lifecycle-specific structure.

## Keep an implemented RFC current with what actually shipped

Keep paths, symbols, defaults, and mechanisms current in the same change that alters them. Rewrite stale facts in place; do not append change history.

When a shipped RFC is unlikely to guide future work, archive its complete triplet through [`archiving-rfcs`](../../skills/archiving-rfcs/SKILL.md) instead of continuing to maintain it.

### This is not a license to rewrite the *decision*

Update factual realization in place. A reversal of the decision or its rationale requires a new RFC and cross-link; a fully superseded old RFC may be deleted only through the consolidation rule in the [RFC rules](../README.md).
