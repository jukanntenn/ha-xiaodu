// opencode hooks 适配器：复用 .claude/hooks/*.py 脚本（单一来源，与
// Claude Code / Codex / ZCode / Trae 共用）。
//
// 差异说明（源码实证，anomalyco/opencode）：
// - opencode 的 hook 是旁路型（(input, output) => Promise<void>），输出无法
//   block 会话，因此只挂 post-edit-format（静默修复），不挂 stop-lint。
// - hook input 不含 cwd（tool.execute.after = {tool, sessionID, callID, args}），
//   项目根用 git rev-parse 解析；脚本从 stdin JSON 的 cwd 字段读取。
// - Edit/Write/apply_patch 工具的 args.filePath 是绝对路径（源码实证）。

import { spawn, spawnSync } from "node:child_process"

function projectRoot(cwd: string): string | undefined {
  const result = spawnSync("git", ["rev-parse", "--show-toplevel"], {
    cwd,
    encoding: "utf8",
  })
  if (result.status !== 0) return undefined
  const root = result.stdout.trim()
  return root || undefined
}

function runHook(
  script: string,
  cwd: string,
  stdinData: Record<string, unknown>,
): Promise<void> {
  return new Promise((resolve) => {
    const child = spawn("python", [script], { cwd })
    child.stdin.write(JSON.stringify(stdinData))
    child.stdin.end()
    child.on("exit", () => resolve())
  })
}

const EDIT_TOOLS = new Set(["edit", "write", "apply_patch"])

export default async function hooks() {
  const root = projectRoot(process.cwd())
  return {
    "tool.execute.after": async (input: {
      tool?: string
      args?: { filePath?: unknown }
    }) => {
      if (!root) return
      if (!input.tool || !EDIT_TOOLS.has(input.tool)) return
      const filePath = input.args?.filePath
      if (typeof filePath !== "string" || !filePath) return
      await runHook(`${root}/.claude/hooks/post-edit-format.py`, root, {
        cwd: root,
        tool_input: { file_path: filePath },
      })
    },
  }
}
