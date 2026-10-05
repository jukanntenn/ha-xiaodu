# Development guide

English | [中文](development.zh.md)

The setup tutorial takes a new contributor from prerequisites to a checked checkout. The contributor reference that follows covers the daily workflow and the repository's tool integrations.

## Setup tutorial

### Prerequisites

Python >= 3.13 and Home Assistant >= 2026.1.0; [uv](https://docs.astral.sh/uv/) as the package manager; git, the [GitHub CLI](https://cli.github.com/), and [ripgrep](https://github.com/BurntSushi/ripgrep) for the harness toolchain.

### First-time setup

From a fresh clone run `uv sync`, `uv tool install "harness-deepseek-harness @ git+https://github.com/jukanntenn/harness-deepseek-harness@main"`, `prek install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg`, then `hdsh worktree install`; setup is complete when `prek run --all-files` passes end to end.

## Contributor reference

### Project layout

One name identifies one concept across the directory, the interface, and any id prefix; the full component map is [architecture.md](architecture.md).

### Daily commands

`prek run --all-files` — the full gate set CI runs. `prek run --group check --group hdsh --all-files` — tests plus the hdsh documentation gates. `uv run pytest tests/test_light.py` — one focused test file. `uv run basedpyright` — type check against the frozen baseline. `hdsh pairing list` — which bilingual pairs still need a counterpart; `hdsh pairing record <anchor>` records one after review. Documentation gates and the bilingual pairing workflow follow the [bilingual documentation contract](i18n/README.md); the gate corpora are configured in `.hdsh/docs.manifest.json` and `.hdsh/pairing.manifest.json`.

### TODO markers

This repository keeps no TODO markers in source; open an Issue instead, and record decisions as RFCs under `.agents/rfcs/`.
