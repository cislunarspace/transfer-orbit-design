"""轨道绘图工具（OrbitVisualizer / FamilyPlotter / PlotConfig）。

收编自 e2m2e 5.6.5 ``tools/viz``（Apache-2.0，原作者：天疆说）。e2m2e 5.6.6
删除该模块（上游 commit #391「示例各自实现绘图」），本项目 GUI 画布与
plot/ 脚本依赖它，故收编进 ``src/commons/viz`` 由本项目自维护；与原版的
唯一差异是内部相对导入改为绝对导入，并剔除项目未用的 TransferPlotter。

English: orbit plotting toolkit (OrbitVisualizer / FamilyPlotter /
PlotConfig). Absorbed from e2m2e 5.6.5 ``tools/viz`` (Apache-2.0,
original author: 天疆说). e2m2e 5.6.6 deleted that module (upstream
commit #391, "let each example implement its own plotting"), but this
project's GUI canvas and plot/ scripts depend on it, so it is
maintained here under ``src/commons/viz``; the only differences from
the original are internal relative imports changed to absolute ones
and removal of the unused TransferPlotter.
"""

from __future__ import annotations

from e2m2e.data.templates.enums import ProjectionPlane

from .base import OrbitVisualizer
from .config import BODY_ICON_PATH_ENV, BODY_ICON_SCALE_ENV, PlotConfig
from .family import FamilyPlotter

__all__ = [
    "OrbitVisualizer",
    "ProjectionPlane",
    "PlotConfig",
    "BODY_ICON_PATH_ENV",
    "BODY_ICON_SCALE_ENV",
    "FamilyPlotter",
]
