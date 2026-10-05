# RFC: User-account support in the Issue/PR policy engine

Status: implemented

English | [中文](2026-09-08-user-account-issue-policy.zh.md)

## Problem

The policy engine was written against three organization-only GitHub mechanisms: the ProjectV2 GraphQL entry `organization(login:)`, the native Issue Type as the Issue classification carrier, and a GitHub App holding the organization-projects permission as the Project credential. A repository owned by a personal account has none of the three — the GraphQL `organization` field resolves only organizations, user-account repositories carry no native Issue Types at all (so every Issue would fail classification forever), and GitHub Apps cannot be granted access to user-owned Projects: only a classic PAT with the `project` scope can read or write them, while `GITHUB_TOKEN` never sees Projects of either ownership. The framework's audience includes personal-account repositories — this repository itself is one — so one ruleset must govern both account kinds, and the difference between a deployment flavor and a policy change has to live somewhere explicit rather than in scattered conditionals.

## Decision

### One engine, two deployment flavors

`config.json` names the account kind explicitly: `owner` (renamed from `organization`) plus `accountType`, validated against the closed set `organization` | `user` at load. The flavor drives every account-dependent branch — the GraphQL entry, the classification carrier, and the workflow credential path — from one source of truth; a wrong `accountType` fails loudly at Project resolution, never silently.

### The GraphQL entry follows the owner kind

The Project query declares both top-level entries, `organization(login: $owner) @include(if: $isOrganization)` and `user(login: $owner) @include(if: $isUser)`, with identical `projectV2` selections; the client takes whichever account block the flavor enabled. One query, one ProjectV2 contract.

### Classification: one taxonomy, carrier by platform

The five-name classification (Idea, Feature, Bug, Research, Task) is unchanged. Organization deployments keep the native Issue Type. User deployments carry it as exactly one `type/*` label (`type/idea` … `type/task`); `classification_from_labels` normalizes the label carrier to the canonical name at the snapshot boundary, so `validate_issue` checks one carrier-independent value. Organization-account Issues must not carry `type/*` labels — a shadow taxonomy beside the native field — and pull requests must not carry them on either flavor: `type/*` joins `source/*` as an Issue-only namespace, mirroring the Issue-side `kind/*` ban.

### Credentials follow the flavor

Organization deployments are unchanged: one GitHub App (Issues and Pull requests read/write, organization Projects read/write) mints the Project-read token in the policy workflow and the REST-plus-GraphQL token in the lifecycle workflow. User deployments cannot grant an App Project access, so REST — including audit comments — runs on `github.token` (the `github-actions[bot]` identity the marker lookup already expects) and ProjectV2 GraphQL runs on a classic PAT with only the `project` scope, stored as `HDSH_PROJECT_PAT` and held by a dedicated machine account. Each workflow resolves the flavor from the checked-out `config.json` and fails with a named error when the matching credential is missing; the later `||` token selections are proven by that resolution step, not silent defaults.

### The identity model

The developer identity — the human and the agent bound to it — authors pull requests from the owning account. The machine account exists for two duties: its `project`-scope PAT drives board automation, so Project status writes carry an actor distinct from every human; and, provisionally, a human reviews and approves pull requests through it in the browser, because a sole maintainer cannot approve their own pull requests and a third dedicated review account is not worth its management cost. Two operational rules keep the semantics intact: manual board moves happen only as the owning human (a machine-account drag would masquerade as automation and become regressable), and no repo-scoped token of the machine account ever exists in CI or locally — with a `project`-only PAT, every approval under that login is necessarily a human act.

## Verification

`tests/policy/` pins the closed `accountType` set and the renamed `owner` field, the query variables selecting the organization or user entry, user-entry Project resolution, label-to-canonical normalization at the snapshot boundary, the organization-account `type/*` ban, the pull-request `type/*` ban, and the unchanged five-name classification. The two workflow files' flavor-resolution steps, credential-presence failures, conditional token minting, and the `github.token` REST path for user deployments are covered by review of the workflow files. First live exercise: this repository's own Issue and pull-request flow on the `jukanntenn` account.

## Alternatives considered

**Support organizations only and document "use an organization".** Rejects the personal-account audience the framework targets; this repository could not dogfood its own gates.

**A second client class per flavor.** `ProjectV2` has one shape; two clients duplicate every snapshot and mutation for a one-field difference.

**Resolve the owner kind from the API instead of config.** The rules are pure functions over snapshots and cannot see the wire, so the flavor would gain a second truth source that can disagree with the config; one validated field fails louder and earlier.

**Carry the classification on `type/*` labels for both flavors.** Uniform, but it abandons the native Issue Type organization accounts get for free — list filtering, type views — replacing the stronger carrier with the weaker one wherever both exist.

**A marker comment as the status-actor journal (the markpost design).** Reading GitHub's own `PROJECT_V2_ITEM_STATUS_CHANGED_EVENT` actor needs no journal comments on Issues and works identically once the PAT belongs to a machine account; the marker compensates for a PAT owned by the human, which the identity model above already avoids.

**A GitHub App on the user account for REST plus a PAT for GraphQL.** Two credentials for no additional guarantee — the board-write actor would still be the PAT's account — while `github.token` keeps REST at repository scope with zero extra setup.

**A third dedicated review-and-approval account.** The clean attribution (approvals never display under the bot login) is not worth a second machine identity to secure and rotate for a sole maintainer; the `project`-only PAT rule restores the same guarantee by elimination.

## Consequences

- Personal-account repositories adopt the full governance gates — board automation, classification, label taxonomy, lifecycle projection — with one classic PAT as their only additional credential, scoped to Projects alone and unable to read repository content (public repositories; private consumers add `repo`).
- The classification rides labels on user accounts, so the policy cannot use GitHub's native type filtering there: programmatic Issue creation sets the label instead of a GraphQL type id, and the intake templates carry `labels: type/*` frontmatter rather than `type:`.
- The machine account's browser duties mix a human decision record with a bot login: approvals display under the machine account, and the guarantee that they are human rests on the absence of any repo-scoped machine token — an operational rule rather than a platform mechanism. A future dedicated review account, or the inverted polarity (the machine authors, the human approves), can restore attribution without touching the engine.
- Organization deployments keep a single App identity for REST and board writes; the App's permission surface includes Pull requests (read) for lifecycle REST reads, which the earlier record understated.
- Every account-dependent branch flows from one config field; a deployment that changes account kind edits `owner` and `accountType` together, and the workflows' credential checks fail with the named missing secret rather than a token error downstream.
