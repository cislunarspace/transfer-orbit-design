"""mcp-serve 冒烟脚本：spawn → initialize 握手 → tools/list → design_orbit 真调用。

验证本仓 ADR 0023 依赖的链路真实可用，并兼作发布流水线的打包冒烟闸：
design_orbit 走完整星历修正链（懒加载 R2S2 → CalcephBin.open 包内
lte440.bsp → SPICE 内核加载 → 修正收敛），打包漏带任何一环都会在此变红，
坏包发不出去。

用法：
    开发（默认）：uv run e2m2e mcp-serve，cwd=仓库根
    打包：--exe <sidecar 路径> --cwd <resource 根> --kernels <SPICE 内核目录>

一次性与 CI 双用，不进仓库测试套件。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# design_orbit 冒烟参数：HALO L1 北族，10 天短弧（venv 实测秒级收敛），
# 走 segmented 星历修正——恰好覆盖 R2S2/SPICE 全链路。
DESIGN_ARGS = {
    "orbit_type": "HALO",
    "collinear_point": 1,
    "north_south": 1,
    "amplitude": 20000.0,
    "phase": 0.5,
    "epoch": [2024, 1, 1, 0, 0, 0],
    "duration": 864000,
    "output_step": 3600,
    "correction_method": "segmented",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", help="打包 sidecar 可执行文件路径（缺省走 dev uv 拉起）")
    parser.add_argument("--cwd", default=REPO_ROOT, help="子进程工作目录")
    parser.add_argument(
        "--kernels",
        help="SPICE 内核目录，写入子进程 SPICE_KERNEL_DIR（打包冒烟必传）",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    command = [args.exe, "mcp-serve"] if args.exe else ["uv", "run", "e2m2e", "mcp-serve"]

    env = os.environ.copy()
    if args.kernels:
        env["SPICE_KERNEL_DIR"] = os.path.abspath(args.kernels)

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",  # mcp-serve 输出 UTF-8；Windows 默认 GBK 会炸
        errors="replace",
        cwd=args.cwd,
        env=env,
    )

    def send(msg: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def read_until(req_id: int) -> dict:
        assert proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if not line:
                err = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(f"mcp-serve 提前退出。stderr:\n{err[-2000:]}")
            msg = json.loads(line)
            if msg.get("id") == req_id:
                return msg

    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        }
    )
    init_resp = read_until(1)
    server = init_resp.get("result", {}).get("serverInfo", {})
    print(f"initialize → serverInfo={json.dumps(server, ensure_ascii=False)}")

    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_resp = read_until(2)
    tools = tools_resp.get("result", {}).get("tools", [])
    print(f"tools/list → {len(tools)} 个工具")
    if not tools:
        print("FAIL: tools/list 为空")
        proc.kill()
        return 1

    send(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "design_orbit", "arguments": DESIGN_ARGS},
        }
    )
    call_resp = read_until(3)
    result = call_resp.get("result", {})
    is_error = result.get("isError", False)
    content = result.get("content", [])
    text = content[0].get("text", "") if content else ""
    print(f"tools/call design_orbit → isError={is_error}, text={text[:400]}")

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

    if is_error or "converged" not in text:
        print("FAIL: design_orbit 未收敛或返回错误")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
