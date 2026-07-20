"""optimize_leo_to_dro 转移设计脚本。

本模块读取已生成的轨道或搜索结果 JSON，在地月 CR3BP 单位体系中执行搜索、验证或 NLP 优化。网格类脚本输出候选转移，优化类脚本读取候选并最小化速度增量或插入误差，结果写入 output/transfer 相关目录。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.leo_to_dro.optimize_leo_to_dro --help
"""


from __future__ import annotations

import logging

# 复用 GEO→DRO 优化脚本的全部逻辑，通过 main() 的显式参数覆盖默认范围。
import tod.transfers.geo_to_dro.optimize_geo_to_dro as base_opt
from pathlib import Path

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent

# LEO→DRO 与 GEO→DRO 的搜索范围差异：
#   alpha: [1.2, 2.0]  vs  [1.0, 1.5]
#   T:     [5.0, 80.0] vs  [5.0, 60.0]
# 这些差异通过 main() 的关键字参数显式传递，不再修改模块常量。
_LEO_ALPHA_MIN = 1.2
_LEO_ALPHA_MAX = 2.0
_LEO_T_MAX = 80.0

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
    base_opt.main(
        alpha_min=_LEO_ALPHA_MIN,
        alpha_max=_LEO_ALPHA_MAX,
        t_max=_LEO_T_MAX,
    )


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='optimize_leo_to_dro',
    description='优化',
    script_path='tod/transfers/leo_to_dro/optimize_leo_to_dro.py',
    output_dir='output/transfer',
    group_label='LEO→DRO',
    cli_params=[
        CliParam('--search-file', '搜索结果文件', 'str', '', help='网格搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '1.2', help='alpha 搜索下界。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '2.0', help='alpha 搜索上界。'),
        CliParam('--t-min', '转移时间下界', 'float', '5.0', help='转移时间下界（无量纲）。', unit_group='time', default_unit='days'),
        CliParam('--t-max', '转移时间上界', 'float', '80.0', help='转移时间上界（无量纲）。', unit_group='time', default_unit='days'),
        CliParam('--t-ins-min', '插入时间下界', 'float', '0.0', help='DRO 插入时间下界。', unit_group='time', default_unit='days'),
        CliParam('--t-ins-max', '插入时间上界', 'float', '10.0', help='DRO 插入时间上界。', unit_group='time', default_unit='days'),
        CliParam('--velocity-angle-tol', '速度平行性容差', 'float', '', help='速度平行性容差（度）', unit_group='angle'),
        CliParam('--nlp-maxiter', 'NLP 最大迭代', 'int', '100', help='NLP 最大迭代次数。'),
        CliParam('--nlp-ftol', 'NLP 函数容差', 'float', '1e-8', help='NLP 函数容差。'),
        CliParam('--top-k', '前 K 个可行解', 'int', '', help='取前 K 个可行解优化。'),
        CliParam('--max-cases', '最大案例数', 'int', '', help='最大优化案例数。'),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行 worker 数。'),
    ],
)
