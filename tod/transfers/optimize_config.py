"""optimize_config 转移设计脚本。

本模块读取已生成的轨道或搜索结果 JSON，在地月 CR3BP 单位体系中执行搜索、验证或 NLP 优化。网格类脚本输出候选转移，优化类脚本读取候选并最小化速度增量或插入误差，结果写入 output/transfer 相关目录。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.optimize_config --help
"""

import os
import time

def blas_threads_per_worker(default_limit: int = 1) -> int:
    """获取每个 worker 的 BLAS 线程数。
    
    Args:
        default_limit: 默认线程限制。
    
    Returns:
        线程数（至少为 1）。
    """
    env_val = os.environ.get("OPTIMIZE_BLAS_THREADS_PER_WORKER", "").strip()
    if env_val:
        return max(1, int(env_val))
    return default_limit

def apply_blas_env_for_child_processes(n_threads: int, *, overwrite: bool = True) -> None:
    """为子进程设置 BLAS 环境变量。
    
    Args:
        n_threads: 线程数。
        overwrite: 是否覆盖已有的环境变量。
    
    Returns:
        None。
    """
    for key in [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        if overwrite:
            os.environ[key] = str(n_threads)
        else:
            os.environ.setdefault(key, str(n_threads))

class OptimizationProgress:
    """优化进度跟踪器。
    
    记录优化过程中成功/失败案例数和最佳目标值。
    """
    def __init__(self):
        self.total_cases = 0
        self.start_time = 0.0
        self._iter = 0
        self._successes = 0
        self._failures = 0
        self._best_obj = float("inf")

    def start_case(self, k, n_total, global_idx):
        """开始处理一个优化案例。
        
        Args:
            k: 当前案例索引。
            n_total: 总案例数。
            global_idx: 全局索引。
        
        Returns:
            None。
        """
        if self.start_time == 0:
            self.start_time = time.perf_counter()
        self._iter = 0

    def finish_case(self, success, obj_value):
        """完成一个优化案例。
        
        Args:
            success: 是否成功。
            obj_value: 目标函数值。
        
        Returns:
            None。
        """
        if success:
            self._successes += 1
            self._best_obj = min(self._best_obj, obj_value)
        else:
            self._failures += 1

    def get_snapshot(self):
        """获取当前进度快照。
        
        Returns:
            包含迭代次数、成功/失败数和最佳目标值的字典。
        """
        return {
            "iter": self._iter,
            "successes": self._successes,
            "failures": self._failures,
            "best_obj": self._best_obj,
        }
