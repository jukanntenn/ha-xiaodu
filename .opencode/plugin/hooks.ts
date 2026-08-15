import { resolve } from "node:path";
import type { Plugin } from "@opencode-ai/plugin";

/**
 * OpenCode plugin: thin adapters over prek (the single source of truth).
 *
 *   1. PostToolUse formatting - delegates every write/edit/apply_patch to
 *      `prek run --group format --files <paths>`; no formatter logic lives
 *      here, so it can never drift from prek/commit/CI. Best-effort, never
 *      blocks the session.
 *   2. Session-end lint gate - OpenCode's `event` hooks are fire-and-forget
 *      and cannot return a `{"decision":"block"}` like Claude's Stop hook.
 *      Instead, on the first `session.idle` of each real user turn, this hook
 *      runs `prek run --group lint --all-files` (read-only gates: ruff,
 *      codespell, basedpyright lock, import-linter, deptry, ...) and, if it
 *      fails, injects a synthetic user message via `client.session.prompt()`
 *      so the agent keeps working. Mirrors Claude's `stop_hook_active`: at
 *      most ONE feedback per real user prompt; subsequent idles in the same
 *      turn stand down, and a fresh real user message resets the gate.
 *
 * Plugins are stateful in OpenCode (the module is imported once and the hook
 * object is kept alive for the instance lifetime), so the module-level
 * `turnState` map persists across events within a process.
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
      const paths = extractPaths(args.filePath, args.patchText).map((p) =>
        p.startsWith("/") ? p : `${PROJECT_ROOT}/${p}`,
      );
      if (paths.length === 0) return;
      // Best-effort formatting via prek, never block the session.
      await $`prek run --group format --files ${paths}`.quiet().nothrow();
    },

    event: async ({ event }) => {
      if (event.type !== "session.idle") return;
      const sessionID = (event.properties as { sessionID?: string } | undefined)
        ?.sessionID;
      if (!sessionID) return;

      const state = turnState.get(sessionID) ?? { feedbackGiven: false };
      if (state.feedbackGiven) return;

      const gate = await $`prek run --group lint --all-files`
        .cwd(PROJECT_ROOT)
        .quiet()
        .nothrow();
      if (gate.exitCode === 0) return;

      state.feedbackGiven = true;
      turnState.set(sessionID, state);

      const output = (
        gate.stdout.toString("utf8") + gate.stderr.toString("utf8")
      ).trim();

      await client.session
        .prompt({
          path: { id: sessionID },
          body: {
            parts: [
              {
                type: "text",
                synthetic: true,
                text: [
                  `prek（lint 组）发现问题，完成前必须修复。`,
                  ``,
                  `诊断输出：`,
                  output,
                  ``,
                  `要求：`,
                  `1. 修复上述全部诊断；禁止用 # noqa、行内禁用或 type: ignore 压制——除非能说明是误报。`,
                  `2. 若诊断来自 basedpyright 且提示 "went up/down by N"（baseline 漂移）：运行 \`uv run basedpyright --writebaseline\` 重生成 \`.basedpyright/baseline.json\`，与代码改动同笔提交。真实类型错误则修代码，禁止动 baseline 掩盖。`,
                  `3. 修改后自行运行 \`prek run --group lint --all-files\` 验证退出码为 0，再结束。`,
                  `Do not end your turn until the check passes.`,
                ].join("\n"),
              },
            ],
          },
        })
        .catch(() => {});
    },
  };
};
