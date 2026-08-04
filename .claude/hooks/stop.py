#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys

REASON_TEMPLATE = """ruff check found lint errors it could not auto-fix. Resolve them before finishing.

Diagnostics:
<ruff_output>
{diagnostics}
</ruff_output>

Required:
1. Fix every diagnostic above with a real code change. Do not silence them with `# noqa`, inline rule disables, or `type: ignore` - only treat a diagnostic as a false positive if you can justify why.
2. After editing, run `uv run ruff check` yourself to verify the tree is clean.
3. Only attempt to finish again once that command exits 0 with no output.

This enforcement fires once per turn - the stop hook will not block a second time. If you stop again with lint errors remaining, they will slip through to CI. Verify before you finish."""

BASELINE_REASON_TEMPLATE = """basedpyright (--baselinemode=lock) failed. Either baseline drifted or a real type error appeared.

Diagnostics:
<basedpyright_output>
{output}
</basedpyright_output>

Two cases - read the output to tell which:
1. "went down by N" / "went up by N" = baseline drift. The error count changed because your code change added or removed a baselined type error. Fix by running `uv run basedpyright --writebaseline` and committing the regenerated `.basedpyright/baseline.json` together with your code change in the same commit. Never let the hook or CI write the baseline automatically.
2. Real type errors (errors > 0 in the summary line) = your code introduced a new, non-baselined type error. Fix the code; do NOT touch the baseline to silence it.

After editing, run `uv run basedpyright --baselinemode=lock` yourself to verify it exits 0.

This enforcement fires once per turn - the stop hook will not block a second time. Verify before you finish."""


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    if payload.get("stop_hook_active"):
        return

    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--fix"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("[stop-hook] uv not found on PATH; skipping lint gate\n")
        return

    if result.returncode != 0:
        diagnostics = "\n".join(
            line
            for line in (result.stdout + result.stderr).splitlines()
            if line.strip()
        )
        sys.stderr.write(
            json.dumps(
                {
                    "decision": "block",
                    "reason": REASON_TEMPLATE.format(diagnostics=diagnostics),
                }
            )
            + "\n"
        )
        return

    # ruff passed - now gate on basedpyright baseline drift (lock mode, same as CI).
    try:
        bp = subprocess.run(
            ["uv", "run", "basedpyright", "--baselinemode=lock"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("[stop-hook] uv not found on PATH; skipping type gate\n")
        return

    if bp.returncode != 0:
        output = "\n".join(
            line for line in (bp.stdout + bp.stderr).splitlines() if line.strip()
        )
        sys.stderr.write(
            json.dumps(
                {
                    "decision": "block",
                    "reason": BASELINE_REASON_TEMPLATE.format(output=output),
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
