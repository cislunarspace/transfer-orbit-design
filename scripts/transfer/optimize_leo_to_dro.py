"""
LEO → DRO NLP 优化

与 optimize_geo_to_dro.py 结构完全一致，仅调整默认参数范围。
LEO 出发需要更大的 alpha 和更长的转移时间。

运行: python scripts/transfer/optimize_leo_to_dro.py

注: 此脚本通过修改 optimize_geo_to_dro.py 的默认参数实现，
    如需更深定制可直接修改该脚本。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 复用 GEO→DRO 优化脚本的全部逻辑
# 仅覆盖默认参数
import scripts.transfer.optimize_geo_to_dro as base_opt

project_root = Path(__file__).resolve().parent.parent.parent

# 覆盖默认参数（在 import 后修改）
base_opt.ALPHA_MIN = 1.2
base_opt.ALPHA_MAX = 2.0
base_opt.T_MIN = 5.0
base_opt.T_MAX = 80.0
base_opt.T_INS_MAX = 10.0

# LEO 搜索结果文件（运行前更新）
base_opt.SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_leo_dro_UPDATE_ME.json"
)


def main() -> None:
    print("=" * 70, flush=True)
    print("LEO → DRO 转移 NLP 优化", flush=True)
    print("=" * 70, flush=True)
    base_opt.main()


if __name__ == "__main__":
    main()
