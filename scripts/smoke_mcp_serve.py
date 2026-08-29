"""mcp-serve 冒烟脚本：spawn → initialize 握手 → notifications/initialized → tools/list。
验证本仓 ADR 0023 依赖的链路真实可用。用完即弃，不进仓库测试套件。
"""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    proc = subprocess.Popen(
        ["uv", "run", "e2m2e", "mcp-serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",  # mcp-serve 输出 UTF-8；Windows 默认 GBK 会炸
        errors="replace",
        cwd=r"C:\Users\ouyangjiahong\codes\transfer-orbit-design\.claude\worktrees\feat+mcp",
    )

    def send(msg: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def read_line() -> dict:
        assert proc.stdout is not None
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"mcp-serve 提前退出。stderr:\n{err[-2000:]}")
        return json.loads(line)

    send({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "0"},
        },
    })
    init_resp = read_line()
    print("initialize →", json.dumps(init_resp, ensure_ascii=False)[:400])

    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_resp = read_line()
    tools = tools_resp.get("result", {}).get("tools", [])
    print(f"tools/list → {len(tools)} 个工具:")
    for t in tools:
        print(f"  - {t['name']}: {t.get('description', '')[:60]}")

    send({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "catalog_query", "arguments": {}},
    })
    call_resp = read_line()
    result = call_resp.get("result", {})
    is_error = result.get("isError", False)
    content = result.get("content", [])
    text = content[0].get("text", "")[:300] if content else ""
    print(f"tools/call catalog_query → isError={is_error}, text={text!r}")

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("OK" if not is_error else "FAIL")
    return 0 if not is_error else 1


if __name__ == "__main__":
    sys.exit(main())
