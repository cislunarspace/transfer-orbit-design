"""下载 SPICE 内核文件到 ``kernels/``，供星历动力学测试与运行使用。

实现见 ``src.commons.kernels``（下载逻辑、可用性判断、用户数据目录）。
本脚本是其 CLI 包装，保持原有命令行行为。

用法：
    python scripts/download_kernels.py [--kernel-dir DIR]

默认内核目录：仓库根 ``kernels/``（与 ``src.commons.paths.detect_kernel_dir``
的首选搜索路径一致）。

鉴权：GitHub API 未鉴权限速 60 次/小时，单次 setup 足够；CI 或受限环境设
``GH_TOKEN`` 走鉴权通道。
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.commons.kernels import RELEASE, download_kernels  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 kernels-v1 release 下载 SPICE 内核到 kernels/（幂等）"
    )
    parser.add_argument("--kernel-dir", type=pathlib.Path, default=ROOT / "kernels")
    args = parser.parse_args()

    fetched, skipped = download_kernels(args.kernel_dir)
    print(
        f"{RELEASE}: 下载 {fetched} 个内核，跳过 {skipped} 个（已存在）→ {args.kernel_dir}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
