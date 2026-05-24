"""optimize_config 转移设计脚本。

本模块读取已生成的轨道或搜索结果 JSON，在地月 CR3BP 单位体系中执行搜索、验证或 NLP 优化。网格类脚本输出候选转移，优化类脚本读取候选并最小化速度增量或插入误差，结果写入 output/transfer 相关目录。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.optimize_config --help
"""


import os
import time


def blas_threads_per_worker(default_limit: int = 1) -> int:
    """执行 blas_threads_per_worker 对应的处理逻辑。
    
    Args:
        default_limit: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    env_val = os.environ.get("OPTIMIZE_BLAS_THREADS_PER_WORKER", "").strip()
    if env_val:
        return max(1, int(env_val))
    return default_limit


def apply_blas_env_for_child_processes(n_threads: int, *, overwrite: bool = True) -> None:
    """执行 apply_blas_env_for_child_processes 对应的处理逻辑。
    
    Args:
        n_threads: 调用方传入的参数值。
        overwrite: 调用方传入的参数值。
    
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
    """表示 OptimizationProgress 相关的数据结构或行为。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    def __init__(self):
        self.total_cases = 0
        self.start_time = 0.0
        self._iter = 0
        self._successes = 0
        self._failures = 0
        self._best_obj = float("inf")

    def start_case(self, k, n_total, global_idx):
        """执行 start_case 对应的处理逻辑。
        
        Args:
            k: 调用方传入的参数值。
            n_total: 调用方传入的参数值。
            global_idx: 调用方传入的参数值。
        
        Returns:
            None。
        """
        if self.start_time == 0:
            self.start_time = time.perf_counter()
        self._iter = 0

    def finish_case(self, success, obj_value):
        """执行 finish_case 对应的处理逻辑。
        
        Args:
            success: 调用方传入的参数值。
            obj_value: 调用方传入的参数值。
        
        Returns:
            None。
        """
        if success:
            self._successes += 1
            self._best_obj = min(self._best_obj, obj_value)
        else:
            self._failures += 1

    def get_snapshot(self):
        """执行 get_snapshot 对应的处理逻辑。
        
        Returns:
            函数执行结果。
        """
        return {
            "iter": self._iter,
            "successes": self._successes,
            "failures": self._failures,
            "best_obj": self._best_obj,
        }
