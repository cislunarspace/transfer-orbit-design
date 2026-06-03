"""optimize_leo_to_dro 转移设计脚本。

本模块读取已生成的轨道或搜索结果 JSON，在地月 CR3BP 单位体系中执行搜索、验证或 NLP 优化。网格类脚本输出候选转移，优化类脚本读取候选并最小化速度增量或插入误差，结果写入 output/transfer 相关目录。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.leo_to_dro.optimize_leo_to_dro --help
"""


from __future__ import annotations

import logging

# 复用 GEO→DRO 优化脚本的全部逻辑
# 仅覆盖默认参数
import tod.transfers.geo_to_dro.optimize_geo_to_dro as base_opt
from pathlib import Path

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent

# 覆盖默认参数（在 import 后修改）
base_opt.ALPHA_MIN = 1.2
base_opt.ALPHA_MAX = 2.0
base_opt.T_MIN = 5.0
base_opt.T_MAX = 80.0
base_opt.T_INS_MAX = 10.0

# 旧版 ``search_leo_dro_UPDATE_ME.json`` 占位默认路径已被 issue #183 移除：
# LEO→DRO 优化器现在要求用户显式传 ``--search-file`` 或 ``--auto-latest``。
# 想跑通：
#   uv run python -m tod.transfers.leo_to_dro.optimize_leo_to_dro \
#       --auto-latest --auto-latest-dro
# 或显式：
#   uv run python -m tod.transfers.leo_to_dro.optimize_leo_to_dro \
#       --search-file output/transfer/search_leo_dro_*.json \
#       --dro-file output/dro/dro_*.json


def main() -> None:
    """执行脚本主流程。

    Returns:
        None。
    """
    logger.info("=" * 70)
    logger.info("LEO → DRO 转移 NLP 优化")
    logger.info("=" * 70)
    base_opt.main()


if __name__ == "__main__":
    main()
