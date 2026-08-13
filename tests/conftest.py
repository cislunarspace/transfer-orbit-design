import os

import matplotlib

matplotlib.use("Agg", force=True)

import pytest

from src.commons.paths import detect_kernel_dir

# SPICE 内核：e2m2e 的闰秒内核搜索路径在 import 时读取 SPICE_KERNEL_DIR，
# 必须在任何 import e2m2e 之前设置（否则 SPICE(NOLEAPSECONDS)）。
# detect_kernel_dir 优先本项目 kernels/，回退同父目录 e2m2e 源码仓库。
_kernel_dir = detect_kernel_dir()
if _kernel_dir:
    os.environ.setdefault("SPICE_KERNEL_DIR", _kernel_dir)


@pytest.fixture(autouse=True)
def _reset_matplotlib_backend():
    """Force Agg backend before each test to prevent TkAgg interference."""
    try:
        import matplotlib.pyplot as plt
        plt.switch_backend("Agg")
    except Exception:
        pass
    yield
