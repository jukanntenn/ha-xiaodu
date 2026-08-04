import { extname, resolve } from "node:path";
import type { Plugin } from "@opencode-ai/plugin";

/**
 * OpenCode plugin: in-process ruff format + lint-fix, and session-end gates.
 *
 * OpenCode's built-in Format service already runs `ruff format` (by extension)
 * after every write/edit/apply_patch, so this plugin does NOT re-implement
 * formatting. It closes three gaps the built-in service leaves open:
 *
 *   1. `ruff check --fix` (lint auto-fix) - the built-in formatter only formats,
 *      it does not apply lint fixes. This hook runs it per-file right after the
 *      write, silently and idempotently (never blocks the agent).
 *   2. Session-end lint gate - OpenCode's `event` hooks are fire-and-forget and
 *      cannot return a `{"decision":"block"}` like Claude's Stop hook. Instead,
 *      on the first `session.idle` of each real user turn, this hook re-runs
 *      `ruff check --fix` across `custom_components/` and, if any errors remain
 *      that ruff cannot auto-fix, injects a synthetic user message via
 *      `client.session.prompt()` so the agent keeps working. Mirrors Claude's
 *      `stop_hook_active`: at most ONE feedback per real user prompt; subsequent
 *      idles in the same turn stand down, and a fresh real user message resets
 *      the gate.
 *   3. Session-end baseline-drift gate - same idle hook also runs
 *      `basedpyright --baselinemode=lock` (same behavior as CI typecheck.yml and
 *      the prek `basedpyright-lock` hook). If the error count changed in either
 *      direction (baseline drift) or a real type error appeared, it injects a
 *      synthetic message telling the agent how to resolve it (rewrite baseline
 *      via `--writebaseline` for drift, fix code for real errors). The two gates
 *      share the same `turnState` feedback guard, so each emits at most once per
 *      turn; if ruff already triggered feedback, basedpyright waits for the next
 *      idle (or vice versa).
 *
 * Plugins are stateful in OpenCode (the module is imported once and the hook
 * object is kept alive for the instance lifetime), so the module-level
 * `turnState` map persists across events within a process.
 *
 * See docs/agent-hooks.md for the full design.
 */

const PATCH_FILE_RE = /^\*\*\* (?:Update|Add) File: (.+)$/;
const PATCH_MOVE_RE = / -> \*\*\* Move to: (.+)$/;

// The desktop app launches the sidecar with cwd=$HOME, so the shell helper's
// relative paths would resolve outside the project. Anchor on the plugin file
// location (always inside the project) instead of the process cwd.
const PROJECT_ROOT = resolve(import.meta.dir, "../..");

// Per-session feedback gate. Resets on a real (non-synthetic) user message,
// sets after the first idle-time feedback. Keyed by sessionID.
const turnState = new Map<string, { feedbackGiven: boolean }>();

function extractPaths(
  filePath: string | undefined,
  patchText: string | undefined,
): string[] {
  if (filePath) return [filePath];
  if (!patchText) return [];
  const paths: string[] = [];
  for (const line of patchText.split("\n")) {
    const m = line.match(PATCH_FILE_RE);
    if (!m) continue;
    const move = m[1].match(PATCH_MOVE_RE);
    paths.push((move ? move[1] : m[1]).trim());
  }
  return paths;
}

export const HooksPlugin: Plugin = async ({ $, client }) => {
  return {
    "chat.message": async (_input, output) => {
      const parts = output.parts as Array<{ synthetic?: boolean }>;
      if (parts.length > 0 && parts.every((p) => p.synthetic)) return;
      turnState.set(output.message.sessionID, { feedbackGiven: false });
    },

    "tool.execute.after": async (input) => {
      if (
        input.tool !== "write" &&
        input.tool !== "edit" &&
        input.tool !== "apply_patch"
      )
        return;
      const args = (input.args ?? {}) as {
        filePath?: string;
        patchText?: string;
      };
      for (const filePath of extractPaths(args.filePath, args.patchText)) {
        switch (extname(filePath)) {
          case ".py":
          case ".pyi":
            await $`uv run ruff check --fix ${filePath}`.quiet().nothrow();
            await $`uv run ruff format ${filePath}`.quiet().nothrow();
            break;
          default:
            break;
        }
      }
    },

    event: async ({ event }) => {
      if (event.type !== "session.idle") return;
      const sessionID = (event.properties as { sessionID?: string } | undefined)
        ?.sessionID;
      if (!sessionID) return;

      const state = turnState.get(sessionID) ?? { feedbackGiven: false };
      if (state.feedbackGiven) return;

      const LINT_ROOT = `${PROJECT_ROOT}/custom_components`;

      // ── Gate 1: ruff lint ──
      await $`uv run ruff check --fix ${LINT_ROOT}`.quiet().nothrow();
      const verify =
        await $`uv run ruff check ${LINT_ROOT} --output-format=concise`
          .quiet()
          .nothrow();
      if (verify.exitCode !== 0) {
        state.feedbackGiven = true;
        turnState.set(sessionID, state);

        const stdout = verify.stdout.toString("utf8");
        const trimmed = stdout.trim();
        const found = trimmed.match(/Found (\d+) error/);
        const errorCount = found
          ? Number(found[1])
          : trimmed
            ? trimmed.split("\n").length
            : 0;

        await client.session
          .prompt({
            path: { id: sessionID },
            body: {
              parts: [
                {
                  type: "text",
                  synthetic: true,
                  text: [
                    `ruff check auto-applied all fixable violations, but ${errorCount} lint error(s) remain that require manual fixes.`,
                    ``,
                    `Remaining diagnostics:`,
                    trimmed,
                    ``,
                    `Requirements:`,
                    `1. Fix ALL of the errors listed above — do not stop after fixing just one.`,
                    `2. Before declaring the task complete, self-verify by re-running: \`uv run ruff check custom_components/\`.`,
                    `3. Only consider the task done when that command exits cleanly with exit code 0.`,
                    `Do not end your turn until the check passes.`,
                  ].join("\n"),
                },
              ],
            },
          })
          .catch(() => {});
        return;
      }

      // ── Gate 2: basedpyright baseline drift (lock mode, same as CI + prek) ──
      // basedpyright scans per pyproject [tool.basedpyright] include, so no path arg.
      const bp =
        await $`uv run basedpyright --baselinemode=lock`.quiet().nothrow();
      if (bp.exitCode !== 0) {
        state.feedbackGiven = true;
        turnState.set(sessionID, state);

        const bpOut = (bp.stdout.toString("utf8") + bp.stderr.toString("utf8")).trim();

        await client.session
          .prompt({
            path: { id: sessionID },
            body: {
              parts: [
                {
                  type: "text",
                  synthetic: true,
                  text: [
                    `basedpyright (--baselinemode=lock) failed. Either the baseline drifted or a real type error appeared.`,
                    ``,
                    `Diagnostics:`,
                    bpOut,
                    ``,
                    `Two cases — read the output to tell which:`,
                    `1. "went down by N" / "went up by N" = baseline drift. The error count changed because your code change added or removed a baselined type error. Fix by running \`uv run basedpyright --writebaseline\` and committing the regenerated \`.basedpyright/baseline.json\` together with your code change in the same commit. Never let the hook or CI write the baseline automatically.`,
                    `2. Real type errors (errors > 0 in the summary line) = your code introduced a new, non-baselined type error. Fix the code; do NOT touch the baseline to silence it.`,
                    ``,
                    `Before declaring the task complete, self-verify by re-running: \`uv run basedpyright --baselinemode=lock\`.`,
                    `Do not end your turn until it exits 0.`,
                  ].join("\n"),
                },
              ],
            },
          })
          .catch(() => {});
      }
    },
  };
};
