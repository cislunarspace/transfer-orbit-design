"""transfer-orbit-design sidecar 入口：以 serve-stdio 模式运行 e2m2e CLI。

打包产物不依赖命令行参数，直接内定子命令；stdin/stdout 走 JSON 行 +
二进制帧协议（e2m2e ADR 0035），由 Tauri 壳拉起（src-tauri/src/lib.rs
的分发期路径，cwd 指安装目录 resource 根）。
"""

from __future__ import annotations

from e2m2e.api.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main(["serve-stdio"]))
