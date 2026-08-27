import os

import matplotlib

matplotlib.use("Agg", force=True)

import pytest

from src.commons.paths import detect_kernel_dir

# SPICE 内核：e2m2e 的闰秒内核搜索路径在 import 时读取 SPICE_KERNEL_DIR，
# SPICE kernels: e2m2e's leap-second kernel search path reads SPICE_KERNEL_DIR at import time;
# 必须在任何 import e2m2e 之前设置（否则 SPICE(NOLEAPSECONDS)）。
# it must be set before any `import e2m2e` (otherwise SPICE(NOLEAPSECONDS)).
# detect_kernel_dir 优先本项目 kernels/，回退同父目录 e2m2e 源码仓库。
# detect_kernel_dir prefers this project's kernels/, falling back to a sibling e2m2e checkout.
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

    Isolate the default orbit-catalog directory into tmp (issue #375).
    When FacadeBridge is not given an explicit catalog_dir it reads
    ``src.commons.paths.CATALOG_DIR`` (repo-root catalog/ by default);
    tests that pass no argument must not pollute the real catalog.
    """
    monkeypatch.setattr("src.commons.paths.CATALOG_DIR", tmp_path / "catalog")
