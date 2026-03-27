"""NLP 批优化：多进程前限制 BLAS/OpenMP 线程，避免过度订阅。"""

from __future__ import annotations

import os


def blas_threads_per_worker(
    *,
    env_var: str = "OPTIMIZE_BLAS_THREADS_PER_WORKER",
    default_limit: int = 1,
) -> int:
    """读取每 worker 的 BLAS 线程数：环境变量优先，否则用 ``default_limit``。"""
    raw = os.environ.get(env_var)
    if raw is not None and raw.strip() != "":
        return max(1, int(raw))
    return max(1, int(default_limit))


def apply_blas_env_for_child_processes(n_threads: int) -> None:
    """ProcessPool 创建前设置 OMP/MKL 等，子进程继承。"""
    s = str(max(1, int(n_threads)))
    for k in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[k] = s
