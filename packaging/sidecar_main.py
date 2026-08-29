"""transfer-orbit-design sidecar 入口：透传子命令运行 e2m2e CLI。

打包产物默认以 serve-stdio 模式运行（无参数时；stdin/stdout 走 JSON 行 +
二进制帧协议，e2m2e ADR 0035，由 Tauri 壳现有工具链路拉起）；带参数时
透传给 e2m2e CLI——AI 助手的标准 MCP 链路以 `mcp-serve` 子命令拉起同一个
可执行文件（本仓 ADR 0023：两条 stdio 链路并存）。
"""

from __future__ import annotations

import sys

from e2m2e.api.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["serve-stdio"]))
