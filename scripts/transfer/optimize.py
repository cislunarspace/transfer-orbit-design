"""
DRO→RO 第二阶段 NLP：初值来自 grid_search 的 ``search_results_*.json``。改下方路径与参数后运行 ``python optimize.py``。

求解器：有 coptpy 时默认 COPT，否则 SciPy；松弛速度约束仅 SciPy。COPT 与 Python 回调多线程并发易静默退出，故 ``COPT_THREADS`` / ``COPT_BAR_THREADS`` 默认 1；仍异常可设 ``SOLVER="scipy"``。

每个 grid 候选单独构造 ``DROTRONLPOptimizer`` 并求解。``N_WORKERS=1`` 顺序执行；``N_WORKERS>1`` 时多进程或线程池（COPT 多 worker 时不宜 ``PARALLEL_BACKEND="thread"``，脚本会改回 process）。

Windows 下并行需保留 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

import json
import multiprocessing
import shutil
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fontTools.misc.timeTools import timestampNow

import e2m2e
from e2m2e.transfer import (
    DROTRONLPOptimizer,
    NLPOptimizationVariables,
    _HAVE_COPT,
    load_orbit_from_json,
    optimize_with_copt,
)

from scripts.utils.common import MU, TU

project_root = Path(__file__).resolve().parent.parent.parent

# --- 输入：grid_search 的 JSON + 与 grid_search 一致的 DRO/RO 轨道 ---
SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_results_200-1001-0.5-2.5-2.299848_3857331829.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857117998.json"
RO_FILE = project_root / "output/ro/ro_31_3857122799.json"

# --- 候选：指定行或排序取 Top ---
# ROW_INDEX 为 int 时只优化该行；为 None 时在可行集中按 SORT_BY 排序后取前 TOP 条
ROW_INDEX: Optional[int] = None
FEASIBLE_ONLY = False
SORT_BY = "min_distance"  # "min_distance" | "dv_total"
TOP = 1

# --- 初值：MAP_ALPHA 将搜索速度投影到 NLP 的 v_inj=α·v；INTEGRATION_DT 用于由 min_distance_idx 估 T0 ---
MAP_ALPHA = True
INTEGRATION_DT: Optional[float] = None  # None -> 1/(24*TU)

RELAXED_VELOCITY = False  # 松弛速度角约束仅 SciPy；与 COPT 同时启用时本行会走 SciPy
VEL_TOL_DEG = 5.0

# NLP 盒约束；全为 None 时：alpha≈(0.5,2.5)，T 上界随候选 transfer_time 放宽，t_ins 用优化器默认
ALPHA_RANGE: Optional[tuple[float, float]] = None
T_RANGE: Optional[tuple[float, float]] = None
T_INS_RANGE: Optional[tuple[float, float]] = None

# --- 求解器：COPT 在 e2m2e 中为 3 变量 + 2 等式约束，耗时主要在回调内轨道积分 ---
SOLVER: Optional[str] = None  # "copt" | "scipy" | None（有 coptpy 则 copt）
COPT_MAX_ITER = 1000
COPT_FALLBACK_TO_SCIPY = True
COPT_THREADS = 1
COPT_BAR_THREADS = 1

# --- 输出 ---
OUTPUT_FILE: Optional[Path] = None  # None -> output/transfer/optimization_from_search_<时间戳>.json
WRITE_LATEST_COPY = True
LATEST_COPY_NAME = "optimization_from_search_latest.json"

# 每条候选独立一次完整 NLP（独立优化器）；N_WORKERS>1 时用进程/线程池，见 main 内对 COPT+thread 的修正
N_WORKERS: Optional[int] = 1  # 1 顺序；None 表示 min(CPU, 候选数)
PARALLEL_BACKEND = "process"  # 多候选时推荐 process（尤其 COPT）


# --- 以下为初值与排序辅助；核心求解在 run_nlp_for_single_row ---


def departure_velocity_search_model(state: np.ndarray, alpha: float) -> np.ndarray:
    """与 ``DROTransferSearch._compute_departure_velocity`` 一致（平面）。"""
    pos = state[:3].astype(np.float64)
    vel = state[3:6].astype(np.float64)
    r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
    if r_xy < 1e-10:
        return vel.copy()
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_radial_comp = float(np.dot(vel, radial))
    v_tangential_comp = float(np.dot(vel, tangential))
    return v_radial_comp * radial + alpha * v_tangential_comp * tangential


def nlp_alpha_from_search_row(row: dict) -> float:
    """使 ``v_nlp = α·v`` 与搜索阶段速度最接近的 α。"""
    ds = row.get("departure_state")
    if ds is None:
        return 1.0
    state = np.asarray(ds, dtype=np.float64).ravel()
    if state.size < 6:
        return 1.0
    alpha_s = float(row.get("alpha", 1.0))
    v_search = departure_velocity_search_model(state, alpha_s)
    vel = state[3:6]
    denom = float(np.dot(vel, vel))
    if denom < 1e-14:
        return 1.0
    a = float(np.dot(v_search, vel) / denom)
    return a


def estimate_t0_from_min_distance_idx(
    row: dict,
    integration_dt: float,
) -> Optional[float]:
    """由 ``min_distance_idx`` 与等间隔输出估计转移时间初值。"""
    mtt = row.get("transfer_time")
    if mtt is None:
        return None
    mtt = float(mtt)
    mi = row.get("min_distance_idx")
    if mi is None:
        return mtt * 0.5
    mi = int(mi)
    n_steps = max(int(mtt / integration_dt) + 1, 2)
    if n_steps <= 1:
        return mtt
    t = float(mi) * (mtt / float(n_steps - 1))
    return float(np.clip(t, 1e-3, mtt))


def t_ins_from_orbit_idx(ro_orbit: Any, orbit_idx: Optional[int]) -> float:
    """RO 离散下标对应的时间初值。"""
    if orbit_idx is None:
        return float(ro_orbit.times[0])
    i = int(orbit_idx) % len(ro_orbit.times)
    return float(ro_orbit.times[i])


def load_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"期望 JSON 数组，得到: {type(data)}")
    return data


def sort_key(row: dict, mode: str) -> float:
    if mode == "min_distance":
        return float(row.get("min_distance") or 1e9)
    if mode == "dv_total":
        d1 = row.get("dv_departure")
        d2 = row.get("dv_insertion")
        s = 0.0
        if d1 is not None:
            s += float(np.asarray(d1, dtype=np.float64).ravel()[0])
        if d2 is not None:
            s += float(np.asarray(d2, dtype=np.float64).ravel()[0])
        return s
    raise ValueError(f"未知 sort-by: {mode}")


def pick_candidates(
    rows: list[dict],
    feasible_only: bool,
    sort_by: str,
    top: int,
    index: Optional[int],
) -> list[tuple[int, dict]]:
    if index is not None:
        if index < 0 or index >= len(rows):
            raise IndexError(f"index={index} 超出 [0, {len(rows)})")
        return [(index, rows[index])]

    filtered: list[tuple[int, dict]] = [
        (i, r) for i, r in enumerate(rows) if not feasible_only or r.get("is_feasible")
    ]
    if not filtered:
        raise RuntimeError("无候选行（检查 --feasible-only 或搜索结果）")

    filtered.sort(key=lambda t: sort_key(t[1], sort_by))
    return filtered[:top]


def run_nlp_for_single_row(
    row_index: int,
    row: dict,
    dro_path: str,
    ro_path: str,
    *,
    integration_dt: float,
    map_alpha: bool,
    solver: str,
    alpha_range: tuple[float, float],
    t_range: tuple[float, float],
    t_ins_range: tuple[float, float],
    relaxed: bool,
    vel_tol_deg: float,
    copt_max_iter: int,
    copt_fallback: bool,
    copt_threads: int,
    copt_bar_threads: int,
    verbose: bool,
) -> Optional[dict[str, Any]]:
    """单行：新建 ``DROTRONLPOptimizer`` 并求解（顺序或并行 worker 各调一次）。"""
    # departure_state：grid 行内 6 维状态；随后加载轨道并在本函数内构造 CR3BP 与优化器（每行一份）
    dep = np.asarray(row.get("departure_state"), dtype=np.float64).ravel()
    if dep.size != 6:
        if verbose:
            print(f"\n跳过行 {row_index}: departure_state 维数不是 6", flush=True)
        return None

    dro_orbit = load_orbit_from_json(str(dro_path))
    ro_orbit = load_orbit_from_json(str(ro_path))

    # 与 SciPy 路径共用同一动力学；COPT 路径在 e2m2e 中通过回调调用 objective / 约束
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    if map_alpha:
        alpha0 = nlp_alpha_from_search_row(row)
    else:
        alpha0 = float(row.get("alpha", 1.0))

    t0 = estimate_t0_from_min_distance_idx(row, integration_dt)
    if t0 is None:
        t0 = float(row.get("transfer_time") or 10.0) * 0.5
    t0 = float(np.clip(t0, t_range[0], t_range[1]))

    oidx = row.get("min_distance_orbit_idx")
    t_ins0 = t_ins_from_orbit_idx(ro_orbit, oidx if oidx is not None else None)
    t_ins0 = float(np.clip(t_ins0, t_ins_range[0], t_ins_range[1]))

    nlp_initial = NLPOptimizationVariables(
        alpha=alpha0,
        transfer_time=t0,
        t_ins=t_ins0,
    )

    if verbose:
        print("\n" + "-" * 70, flush=True)
        print(
            f"行索引 {row_index}  搜索 α={row.get('alpha')}  min_distance={row.get('min_distance')}",
            flush=True,
        )
        print(f"  初值: α={alpha0:.6f}  T={t0:.6f}  t_ins={t_ins0:.6f}", flush=True)
        print("  开始 NLP…", flush=True)

    optimizer = DROTRONLPOptimizer(
        system=system,
        dynamics=dynamics,
        departure_orbit=dro_orbit,
        arrival_orbit=ro_orbit,
        departure_state=dep,
    )
    optimizer.alpha_range = alpha_range
    optimizer.transfer_time_range = t_range
    optimizer.t_ins_range = t_ins_range

    scipy_kw = dict(
        initial_guess=nlp_initial,
        alpha_range=alpha_range,
        transfer_time_range=t_range,
        t_ins_range=t_ins_range,
        use_relaxed_velocity_constraint=relaxed,
        velocity_angle_constraint=np.deg2rad(vel_tol_deg),
        verbose=verbose,
    )

    # COPT 仅实现等式速度约束；松弛角约束时强制 SciPy
    if relaxed and solver == "copt":
        if verbose:
            print(
                "  提示: COPT 仅等式速度约束；本行改用 SciPy（RELAXED_VELOCITY=True）。",
                flush=True,
            )
        result = optimizer.optimize(**scipy_kw)
    elif solver == "copt":
        if not _HAVE_COPT:
            raise RuntimeError(
                "未检测到 coptpy，无法使用 SOLVER=\"copt\"。请安装 coptpy 或设 SOLVER=\"scipy\"。"
            )
        result = optimize_with_copt(
            optimizer,
            initial_guess=nlp_initial,
            fallback_to_scipy=copt_fallback,
            max_iter=copt_max_iter,
            threads=copt_threads,
            bar_threads=copt_bar_threads,
            scipy_fallback_kwargs=scipy_kw,
        )
    else:
        result = optimizer.optimize(**scipy_kw)

    entry: dict[str, Any] = {
        "solver_used": "scipy" if (relaxed and solver == "copt") else solver,
        "search_row_index": row_index,
        "search_snapshot": {
            "alpha": row.get("alpha"),
            "transfer_time": row.get("transfer_time"),
            "min_distance": row.get("min_distance"),
            "is_feasible": row.get("is_feasible"),
        },
        "initial_guess_nlp": {
            "alpha": nlp_initial.alpha,
            "transfer_time": nlp_initial.transfer_time,
            "t_ins": nlp_initial.t_ins,
        },
        "success": result.success,
        "message": result.message,
        "variables": {
            "alpha": result.alpha,
            "transfer_time": result.transfer_time,
            "t_ins": result.t_ins,
        },
        "delta_v": {
            "dv1": result.delta_v1,
            "dv2": result.delta_v2,
            "total": result.objective_value,
        },
        "departure_state": dep.tolist(),
    }
    if hasattr(result.transfer_type, "value"):
        entry["transfer_type"] = result.transfer_type.value
    else:
        entry["transfer_type"] = str(result.transfer_type)

    return entry


def _optimize_task_payload_to_result(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """进程/线程池入口：可 pickle 的 dict，避免直接传闭包。"""
    return run_nlp_for_single_row(
        row_index=payload["row_index"],
        row=payload["row"],
        dro_path=payload["dro_path"],
        ro_path=payload["ro_path"],
        integration_dt=payload["integration_dt"],
        map_alpha=payload["map_alpha"],
        solver=payload["solver"],
        alpha_range=tuple(payload["alpha_range"]),
        t_range=tuple(payload["t_range"]),
        t_ins_range=tuple(payload["t_ins_range"]),
        relaxed=payload["relaxed"],
        vel_tol_deg=payload["vel_tol_deg"],
        copt_max_iter=payload["copt_max_iter"],
        copt_fallback=payload["copt_fallback"],
        copt_threads=payload["copt_threads"],
        copt_bar_threads=payload["copt_bar_threads"],
        verbose=payload["verbose"],
    )


def _resolve_n_workers(requested: Optional[int], n_tasks: int) -> int:
    """将用户配置的 worker 数限制在 [1, n_tasks] 内。"""
    if n_tasks <= 0:
        return 1
    if requested is None:
        return min(multiprocessing.cpu_count(), n_tasks)
    return max(1, min(int(requested), n_tasks))


def main() -> None:
    # 1) 读 search_results、选候选  2) 算 NLP 边界  3) 顺序或并行跑 run_nlp_for_single_row  4) 写 JSON
    print("optimize.py 已启动…", flush=True)

    search_path = Path(SEARCH_RESULTS_FILE).expanduser().resolve()
    if not search_path.is_file():
        raise FileNotFoundError(search_path)

    dro_path = Path(DRO_FILE).expanduser().resolve()
    ro_path = Path(RO_FILE).expanduser().resolve()
    if not dro_path.is_file():
        raise FileNotFoundError(dro_path)
    if not ro_path.is_file():
        raise FileNotFoundError(ro_path)

    integration_dt = INTEGRATION_DT
    if integration_dt is None:
        integration_dt = 1.0 / (24.0 * TU)

    print(
        f"正在读取搜索结果（可能较慢）: {search_path}",
        flush=True,
    )
    rows = load_rows(search_path)
    print(f"已加载 {len(rows)} 行。", flush=True)
    picked = pick_candidates(
        rows,
        feasible_only=FEASIBLE_ONLY,
        sort_by=SORT_BY,
        top=TOP,
        index=ROW_INDEX,
    )

    print("=" * 70, flush=True)
    print("DRO→RO NLP 优化（初值来自 grid_search）", flush=True)
    print("=" * 70, flush=True)
    print(f"搜索结果: {search_path}（共 {len(rows)} 行）", flush=True)
    print(f"DRO: {dro_path}", flush=True)
    print(f"RO: {ro_path}", flush=True)
    print(f"integration_dt（估计 T0）: {integration_dt:.8f}", flush=True)
    map_alpha = MAP_ALPHA
    solver = SOLVER if SOLVER is not None else ("copt" if _HAVE_COPT else "scipy")
    if solver not in ("copt", "scipy"):
        raise ValueError('SOLVER 须为 "copt"、"scipy" 或 None')
    print(f"候选数: {len(picked)}  map_alpha={map_alpha}  solver={solver}", flush=True)
    if solver == "copt" and _HAVE_COPT:
        print(
            f"  COPT: Threads={COPT_THREADS}, BarThreads={COPT_BAR_THREADS}",
            flush=True,
        )

    # T 上界默认随所选候选的最大 transfer_time 略放宽，避免初值贴边
    alpha_range = ALPHA_RANGE if ALPHA_RANGE is not None else (0.5, 2.5)
    mtt_ref = max(
        (float(rows[i].get("transfer_time") or 1.0) for i, _ in picked),
        default=15.0,
    )
    if T_RANGE is not None:
        t_range = (float(T_RANGE[0]), float(T_RANGE[1]))
    else:
        t_range = (1.0, max(30.0, mtt_ref * 1.05))
    t_ins_range = (
        (float(T_INS_RANGE[0]), float(T_INS_RANGE[1]))
        if T_INS_RANGE is not None
        else getattr(DROTRONLPOptimizer, "DEFAULT_T_INS_RANGE", (0.0, 10.0))
    )

    # 多 worker + COPT + thread 会强制改为 process（避免 COPT 与 Python 回调多线程并发问题）
    n_tasks = len(picked)
    n_workers = _resolve_n_workers(N_WORKERS, n_tasks)
    parallel_backend = PARALLEL_BACKEND
    if n_workers > 1 and parallel_backend == "thread" and solver == "copt":
        print("  并行: COPT 与 thread 后端不兼容，已改用 process。", flush=True)
        parallel_backend = "process"

    print(
        f"  并行调度: n_workers={n_workers}（候选 {n_tasks} 条）"
        f"，backend={parallel_backend if n_workers > 1 else 'sequential'}",
        flush=True,
    )

    out_list: list[dict[str, Any]] = []

    def _make_payload(row_index: int, row: dict, *, verbose: bool) -> dict[str, Any]:
        return {
            "row_index": row_index,
            "row": row,
            "dro_path": str(dro_path),
            "ro_path": str(ro_path),
            "integration_dt": integration_dt,
            "map_alpha": map_alpha,
            "solver": solver,
            "alpha_range": [alpha_range[0], alpha_range[1]],
            "t_range": [t_range[0], t_range[1]],
            "t_ins_range": [t_ins_range[0], t_ins_range[1]],
            "relaxed": RELAXED_VELOCITY,
            "vel_tol_deg": VEL_TOL_DEG,
            "copt_max_iter": COPT_MAX_ITER,
            "copt_fallback": COPT_FALLBACK_TO_SCIPY,
            "copt_threads": COPT_THREADS,
            "copt_bar_threads": COPT_BAR_THREADS,
            "verbose": verbose,
        }

    # 顺序模式便于逐行看日志；并行时子进程/线程内 verbose=False，减少输出交错
    if n_workers == 1:
        for row_index, row in picked:
            r = run_nlp_for_single_row(
                row_index,
                row,
                str(dro_path),
                str(ro_path),
                integration_dt=integration_dt,
                map_alpha=map_alpha,
                solver=solver,
                alpha_range=alpha_range,
                t_range=t_range,
                t_ins_range=t_ins_range,
                relaxed=RELAXED_VELOCITY,
                vel_tol_deg=VEL_TOL_DEG,
                copt_max_iter=COPT_MAX_ITER,
                copt_fallback=COPT_FALLBACK_TO_SCIPY,
                copt_threads=COPT_THREADS,
                copt_bar_threads=COPT_BAR_THREADS,
                verbose=True,
            )
            if r is not None:
                out_list.append(r)
    else:
        payloads = [_make_payload(i, r, verbose=False) for i, r in picked]
        Executor = (
            ProcessPoolExecutor
            if parallel_backend == "process"
            else ThreadPoolExecutor
        )
        with Executor(max_workers=n_workers) as ex:
            futures = {
                ex.submit(_optimize_task_payload_to_result, p): p for p in payloads
            }
            completed = 0
            for fut in as_completed(futures):
                completed += 1
                p = futures[fut]
                ri = p["row_index"]
                try:
                    r = fut.result()
                    if r is not None:
                        out_list.append(r)
                    print(
                        f"  [{completed}/{n_tasks}] 完成 search_row_index={ri}",
                        flush=True,
                    )
                except Exception as e:
                    print(
                        f"  [{completed}/{n_tasks}] 失败 search_row_index={ri}: {e}",
                        flush=True,
                    )

    # as_completed 完成顺序不定，按 search_row_index 排序再写出
    out_list.sort(key=lambda e: int(e.get("search_row_index", 0)))

    out_path = (
        Path(OUTPUT_FILE).expanduser().resolve()
        if OUTPUT_FILE is not None
        else project_root
        / "output"
        / "transfer"
        / f"optimization_from_search_{timestampNow()}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "search_results": str(search_path),
                    "dro": str(dro_path),
                    "ro": str(ro_path),
                    "integration_dt": integration_dt,
                    "map_alpha": map_alpha,
                    "solver": solver,
                    "n_workers": n_workers,
                    "parallel_backend": (
                        parallel_backend if n_workers > 1 else "sequential"
                    ),
                    "max_iter_copt": COPT_MAX_ITER,
                    "copt_threads": COPT_THREADS,
                    "copt_bar_threads": COPT_BAR_THREADS,
                    "copt_fallback": COPT_FALLBACK_TO_SCIPY,
                    "have_copt": _HAVE_COPT,
                    "relaxed": RELAXED_VELOCITY,
                    "vel_tol_deg": VEL_TOL_DEG,
                },
                "results": out_list,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    out_abs = out_path.resolve()
    print("\n" + "=" * 70, flush=True)
    print(f"已写入（绝对路径）:\n  {out_abs}", flush=True)
    if WRITE_LATEST_COPY:
        latest = (project_root / "output" / "transfer" / LATEST_COPY_NAME).resolve()
        latest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_abs, latest)
        print(f"已复制最新结果到:\n  {latest}", flush=True)
    print("=" * 70, flush=True)

    if any(not e.get("success") for e in out_list):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断；未完成求解则不会写出结果 JSON。", flush=True)
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        print(
            "\n检查 SEARCH_RESULTS_FILE；求解耗时长时结束前不会写出 JSON。"
            "\n试跑可设 ROW_INDEX=0、SOLVER=\"scipy\"。",
            flush=True,
        )
        sys.exit(1)
