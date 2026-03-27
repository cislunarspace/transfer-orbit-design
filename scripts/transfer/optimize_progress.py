"""串行 NLP：SLSQP 迭代进度与后台监控线程。"""

from __future__ import annotations

import threading
import time
def wall_time() -> float:
    """墙钟秒数（与 ``time.time()`` 一致）。"""
    return time.time()


class OptimizationProgress:
    """串行模式：callback 与监控线程共享的进度。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.case_index: int = -1
        self.total_cases: int = 0
        self.search_index: int = -1  # 对应网格 JSON 下标
        self.iteration: int = 0
        self.objective: float = float("inf")
        self.alpha: float = 0.0
        self.transfer_time: float = 0.0
        self.t_ins: float = 0.0
        self.start_time: float = 0.0
        self.case_start_time: float = 0.0
        self.last_success: bool = False
        self.last_delta_v: float = float("inf")
        self.last_duration: float = 0.0

    def start_case(self, case_idx: int, total: int, search_idx: int) -> None:
        """进入第 ``case_idx`` 条（共 ``total`` 条），对应原始网格下标 ``search_idx``。"""
        with self._lock:
            if self.start_time <= 0:
                self.start_time = wall_time()  # 整条批任务开始时刻
            self.case_index = case_idx
            self.total_cases = total
            self.search_index = search_idx
            self.iteration = 0
            self.objective = float("inf")
            self.alpha = 0.0
            self.transfer_time = 0.0
            self.t_ins = 0.0
            self.case_start_time = wall_time()

    def update_iteration(self, it: int, obj: float, a: float, T: float, tins: float) -> None:
        """由 SLSQP 回调更新当前迭代的序号、目标与变量猜测。"""
        with self._lock:
            self.iteration = it
            self.objective = obj
            self.alpha = a
            self.transfer_time = T
            self.t_ins = tins

    def finish_case(self, success: bool, delta_v: float) -> None:
        """本条 NLP 结束：记录是否成功与 ΔV，并统计耗时。"""
        with self._lock:
            self.last_success = success
            self.last_delta_v = delta_v
            self.last_duration = wall_time() - self.case_start_time

    def get_snapshot(self) -> dict:
        """供监控线程读取当前进度（线程安全拷贝）。"""
        with self._lock:
            return dict(
                case=self.case_index,
                total=self.total_cases,
                search_index=self.search_index,
                iter=self.iteration,
                obj=self.objective,
                alpha=self.alpha,
                T=self.transfer_time,
                tins=self.t_ins,
                duration=self.last_duration,
                last_success=self.last_success,
                last_delta_v=self.last_delta_v,
            )


def make_progress_callback(
    prog: OptimizationProgress, _case_idx: int, _total: int, _search_idx: int
):
    """返回写入 OptimizationProgress 的 SLSQP 回调（若 e2m2e 支持）。"""

    def callback(it: int, obj: float, a: float, T: float, tins: float) -> None:
        """由优化器在每次迭代调用（iter, 目标值, α, T, t_ins）。"""
        prog.update_iteration(it, obj, a, T, tins)

    return callback


def monitor_loop_serial_nlp(prog: OptimizationProgress, interval: float = 2.0) -> None:
    """后台周期性打印当前 case 与迭代信息；最后一条开始后若已有迭代则退出。"""
    while True:
        time.sleep(interval)
        snap = prog.get_snapshot()
        total_elapsed = wall_time() - prog.start_time if prog.start_time > 0 else 0
        if snap["total"] > 0 and snap["case"] >= 0:
            print(
                f"  ▶ case {snap['case']+1}/{snap['total']} "
                f"(search_idx={snap['search_index']}) | "
                f"iter={snap['iter']:4d} | "
                f"α={snap['alpha']:.4f} T={snap['T']:.4f} tins={snap['tins']:.4f} | "
                f"obj={snap['obj']:.6f} | "
                f"elapsed={total_elapsed:.0f}s",
                flush=True,
            )
            if snap["case"] >= snap["total"] - 1 and snap["iter"] > 0:
                break
