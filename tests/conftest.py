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


@pytest.fixture(autouse=True)
def _isolate_catalog_dir(monkeypatch, tmp_path):
    """把默认轨道库目录隔离到 tmp（issue #375）。

    FacadeBridge 未显式传 catalog_dir 时读 ``src.commons.paths.CATALOG_DIR``
    （默认仓库根 catalog/）；测试不显式传参时不允许污染真实库目录。
    """
    monkeypatch.setattr("src.commons.paths.CATALOG_DIR", tmp_path / "catalog")