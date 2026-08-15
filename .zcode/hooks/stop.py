#!/usr/bin/env python3
# ZCode Stop：全仓 lint 门控委托给 prek（lint 组，单一真相源）。本脚本只把 prek
# 退出码翻译成 ZCode 的 block 决定；stopHookActive 守卫防循环（每轮至多拦截
# 一次）。绝不输出 continue: false（在部分平台语义为"停止"且优先级更高）。
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REASON = """prek（lint 组）发现问题，完成前必须修复。

诊断输出：
<prek_output>
{diagnostics}
</prek_output>

要求：
1. 修复上述全部诊断；禁止用 `# noqa`、行内禁用或 `type: ignore` 压制——除非能说明是误报。
2. 若诊断来自 basedpyright 且提示 "went up/down by N"（baseline 漂移）：运行
   `uv run basedpyright --writebaseline` 重生成 `.basedpyright/baseline.json`，与代码
   改动同笔提交。真实类型错误则修代码，禁止动 baseline 掩盖。
3. 修改后自行运行 `prek run --group lint --all-files` 验证退出码为 0，再尝试结束。

本门控每轮只触发一次；再次停止时若仍有错误将漏到 CI，务必先验证。"""


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return
    if payload.get("stopHookActive"):
        return

    try:
        result = subprocess.run(
            ["prek", "run", "--group", "lint", "--all-files"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("[zcode-stop-hook] prek 不在 PATH 上，跳过 lint 门控\n")
        return

    if result.returncode != 0:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": REASON.format(
                        diagnostics=(result.stdout + result.stderr).strip()
                    ),
                }
            )
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
