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

    if result.returncode == 0:
        return

    diagnostics = "\n".join(
        line for line in (result.stdout + result.stderr).splitlines() if line.strip()
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


if __name__ == "__main__":
    main()
    sys.exit(0)
