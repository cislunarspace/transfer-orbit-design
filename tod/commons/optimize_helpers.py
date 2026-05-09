"""优化脚本共享工具：BLAS 线程控制、进度追踪。"""

import os
import time


def blas_threads_per_worker(default_limit: int = 1) -> int:
    env_val = os.environ.get("OPTIMIZE_BLAS_THREADS_PER_WORKER", "").strip()
    if env_val:
        return max(1, int(env_val))
    return default_limit


def apply_blas_env_for_child_processes(n_threads: int) -> None:
    for key in [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[key] = str(n_threads)


class OptimizationProgress:
    def __init__(self):
        self.total_cases = 0
        self.start_time = 0.0
        self._iter = 0
        self._successes = 0
        self._failures = 0
        self._best_obj = float("inf")

    def start_case(self, k, n_total, global_idx):
        if self.start_time == 0:
            self.start_time = time.perf_counter()
        self._iter = 0

    def finish_case(self, success, obj_value):
        if success:
            self._successes += 1
            self._best_obj = min(self._best_obj, obj_value)
        else:
            self._failures += 1

    def get_snapshot(self):
        return {
            "iter": self._iter,
            "successes": self._successes,
            "failures": self._failures,
            "best_obj": self._best_obj,
        }
