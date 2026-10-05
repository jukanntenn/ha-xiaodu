# Contributing guide

English | [中文](CONTRIBUTING.zh.md)

Thank you for spending time on Xiaodu for Home Assistant! Code, tests, documentation, translations, and new device-type support are all welcome. By participating (issues, PRs, Discussions) you agree to follow the [code of conduct](.github/CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report bugs**: use the [bug form](https://github.com/jukanntenn/ha-xiaodu/issues/new?template=bug.yml) and fill in the fields as guided
- **Feature ideas and usage questions**: discuss first in the matching [Discussions](https://github.com/jukanntenn/ha-xiaodu/discussions) category (ideas / Q&A); turn consensus into a concrete feature issue afterwards
- **Code / docs / translations**: start from issues labeled [good first issue](https://github.com/jukanntenn/ha-xiaodu/labels/good%20first%20issue)

## Ground rules

- **Open an issue before any change — including typo fixes.** Open a short issue first, then a PR referencing it; PRs without a linked issue may be closed outright. This keeps work visible and avoids duplicated effort.
- **Reach consensus before non-trivial changes.** New platform support, Bemfa protocol semantics, configuration schema, dependency changes, and lint / gate configuration need maintainer agreement in an issue or Discussions first.

## Development environment

- Python ≥ 3.13, dependencies managed with [uv](https://docs.astral.sh/uv/), Docker (for the local hassfest check)

```bash
uv sync
prek install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
```

> Note: with prek 0.4.11 a bare `prek install` installs only the pre-commit hook; you must pass all three `--hook-type` flags explicitly.

## Common commands

| Command | Purpose |
| --- | --- |
| `uv run pytest tests/test_light.py` | Run a single test file |
| `prek run --all-files` | Full quality gate (local / pre-push / CI share one set — no second standard) |
| `prek run --group check --group hdsh --all-files` | Tests plus the hdsh documentation gates |
| `python3 scripts/hassfest.py` | Integration structure check (manifest / strings / translations) |

## Code conventions

- Constants live in `const.py` and `bemfa/const.py`; no string literals as configuration keys or device type codes
- Class names in PascalCase with a `Xiaodu` / `Bemfa` prefix; file names in snake_case; constants in UPPER_SNAKE_CASE
- Module dependencies stay one-way: platform → entity → coordinator → api / bemfa; no reverse dependencies
- Avoid introducing new `Any`: basedpyright runs in `all` mode, existing `Any` occurrences are frozen in `.basedpyright/baseline.json`, and new ones are rejected; prefer concrete HA types
- In mixed Chinese/English prose, put a space between Chinese and Latin characters; keep branding consistent — first occurrence writes "小度（Xiaodu）" and later ones "小度", Bemfa appears with 巴法云 in tandem, and Home Assistant is never translated

## Testing conventions

- Always use the `aioclient_mock_fixture` pattern (see `tests/conftest.py`) so the real `XiaoduAPI` runs over mocked HTTP; **never patch the API client class itself**
- When several control commands share one URL, distinguish them with a request-body-based `side_effect` handler
- Bemfa MQTT (`BemfaMQTTClient.publish`) may be patched; Bemfa HTTP endpoints go through `aioclient_mock`
- User-level end-to-end scenarios live in `tests/test_e2e/`

## Translation contributions

`strings.json` is the translation source; `translations/en.json` and `translations/zh-Hans.json` are its mirrors. Note that `config.create_entry.*` values **must be strings**, never a dict with a `description` sub-key (that structure belongs to the `step.*` level). Run `python3 scripts/hassfest.py` after changing translations.

## Commits and pull requests

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`), enforced by the commit-msg hook; do not bypass hooks with `--no-verify`
- The CHANGELOG accumulates **user-facing** Chinese descriptions under `## [Unreleased]` (no technical detail)
- Run `prek run --all-files` locally before the PR — CI runs exactly the same gates
- Fill in the PR template checklist and link the issue with `Fixes #NN`; draft PRs for early feedback are welcome

## Scope

- **Directly welcome**: bug fixes, new device types, tests and coverage, documentation, translations
- **Discuss first**: new platform support, Bemfa protocol changes, dependency changes, configuration schema adjustments, lint / gate configuration

## AI-assisted contributions

AI-assisted development is welcome here, with a full instruction system for agents (`AGENTS.md` and `.agents/skills/`). When driving an agent, have it read `AGENTS.md` first. Regardless of whether code was AI-generated, the submitter must fully understand and be able to explain everything in the contribution.

## Getting help

Development questions go to [Discussions](https://github.com/jukanntenn/ha-xiaodu/discussions); the full routing of support channels is in [SUPPORT.md](.github/SUPPORT.md).

## License

By submitting a PR you agree that your contributions are published with the repository under the [MIT License](LICENSE). No CLA is required.
