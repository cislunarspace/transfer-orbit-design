"""批量运行子包：批次定义、批次管理与汇总卡片。

注意：``batch`` 既是本子包名，也是 ``batch.py`` 模块名，二者在
``tod.gui.batch`` 命名空间上冲突（包优先）。因此 ``from tod.gui.batch import
BatchAggregate`` 等历史扁平导入路径在此处通过 re-export 维持兼容。
"""

# 由于 ``tod.gui.batch`` 解析到本包而非旧的同名模块，这里显式 re-export
# ``batch.py`` 的公开符号，保证 ``from tod.gui.batch import ...`` 仍可用。
from tod.gui.batch.batch import *  # noqa: F401,F403
