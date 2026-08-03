# ZCode Hooks

Project-local hook scripts for the ZCode agent (same ruff pipeline as the
Claude/Codex hooks — see `docs/agent-hooks.md`).

- `hooks/post_tool_use.py` — PostToolUse (`Edit|Write`): runs `ruff check --fix`
  then `ruff format` on the edited `.py`/`.pyi` file. Never blocks.
- `hooks/stop.py` — Stop: runs a repo-wide `ruff check --fix`; if unfixable lint
  remains it prints `{"decision":"block","reason":"..."}` (once per turn, guarded
  by the `stopHookActive` flag). ZCode caps Stop continuations at 3 natively.

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
