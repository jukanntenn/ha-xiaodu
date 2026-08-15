# ZCode Hooks

Project-local hook scripts for the ZCode agent. Thin adapters over **prek**
(the single source of truth for all quality gates — same as the
Claude/Codex/opencode hooks and CI; see `prek.toml` and AGENTS.md):

- `hooks/post_tool_use.py` — PostToolUse (`Edit|Write`): runs
  `prek run --group format --files <path>` (ruff autofix/format + whitespace
  hygiene). Never blocks; prek exit 0/1 are both tolerated.
- `hooks/stop.py` — Stop: runs `prek run --group lint --all-files` (ruff,
  codespell, basedpyright lock, import-linter, deptry, uv lock, version sync,
  hassfest, ...). On failure prints `{"decision":"block","reason":"..."}`
  (once per turn, guarded by the `stopHookActive` flag). ZCode caps Stop
  continuations at 3 natively.

## Why there is no `.zcode/config.json` here

The ZCode client UI and official docs support workspace-scope hooks in
`.zcode/config.json`, but the agent runtime on this machine (v2.1.0, WSL server)
**strips them unconditionally** — a "security policy" warning
(`config_project_hooks.ignored`) is logged and no hook runs. Only hooks in the
**user-level** `~/.zcode/cli/config.json` are executed (verified in source and
by log evidence).

The user-level config therefore points at these scripts via
`${ZCODE_PROJECT_DIR}` and guards on file existence, so other workspaces without
this directory are unaffected. Changing the runtime behavior would require a
ZCode update that honors workspace hooks.
