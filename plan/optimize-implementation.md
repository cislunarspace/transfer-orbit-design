# Plan: `optimize.py` — NLP 优化阶段实现说明

| 字段 | 值 |
|------|-----|
| 状态 | in-progress（功能已落地；性能剖析与减算待办） |
| 创建日期 | 2026-03-26 |
| 最后更新 | 2026-03-26 |
| 关联 issue / PR | （可选） |

## 背景与关联

- **用户需求摘要**：补充与 `grid_search` 对等的 **optimize 阶段**实现说明，便于维护、调试与后续性能优化。
- **已查阅的既有 plan**：
  - `plan/feature-orbit-transfer-replication-1.md`（总览、REQ、Phase 2）
  - `plan/grid-search-implementation.md`（搜索阶段）
  - `docs/ways-of-work/plan/feature-orbit-transfer-replication/phase2-planar-dro-ro-transfer/` 下若干 implementation-plan（若存在交叉主题可对照，**以本仓库脚本与 e2m2e 源码为准**）
- **代码入口 / 关键路径**：
  - `scripts/transfer/optimize.py`（本文件描述对象）
  - `e2m2e/e2m2e/transfer/transfer_optimization.py`（`DROTRONLPOptimizer`、`optimize_with_copt`）

---

## 1. 在「搜索–优化」流程中的位置

```
grid_search.py  →  search_results_*.json（含 is_feasible 等）
       ↓
optimize.py      →  optimization_results_*.json（每条对应一次 NLP）
```

- **输入**：`grid_search` 产出的 JSON 数组；脚本筛选 `is_feasible == true` 的记录，按 `min_distance` 升序，再经 `TOP_K_FEASIBLE` / `MAX_CASES` 截断。
- **轨道**：独立指定 `DRO_FILE`、`RO_FILE`（须与生成该 `search_results` 时所用轨道一致，否则初值与物理含义可能对不齐）。
- **NLP 核心**：`e2m2e.transfer.DROTRONLPOptimizer`，优化变量 \(y=\{\alpha, T, t_{ins}\}\)，目标 \(\Delta v_1+\Delta v_2\)，约束见 `transfer_optimization.py`（位置连续、速度平行或松弛等）。

---

## 2. 脚本配置项（`optimize.py` 顶部常量）

| 符号 | 含义 |
|------|------|
| `SEARCH_RESULTS_FILE` | `search_results_*.json` 路径 |
| `DRO_FILE` / `RO_FILE` | DRO/RO 轨道 JSON |
| `ALPHA_MIN` / `ALPHA_MAX` | 与 `grid_search` 中 α 范围一致 |
| `MAX_TRANSFER_TIME` | 与 `grid_search` 中最大转移时间（无量纲 TU）一致 |
| `EARTH_RADIUS` / `MOON_RADIUS` | 撞星半径（DU），与 `grid_search` 一致 |
| `DT`、`INTEGRATOR` | 动力学输出步长上限、积分器名（默认 DOP853） |
| `TOP_K_FEASIBLE` | 只取前 K 条可行解（按 `min_distance`）；`None` 为全部 |
| `MAX_CASES` | 再截断条数；调试用 |
| `N_WORKERS` | `None` → `cpu_count()`；`1` → 串行 |
| `PARALLEL_BACKEND` | `"processes"`（默认）或 `"threads"` |
| `LIMIT_BLAS_THREADS_PER_WORKER` | 多进程下每 worker 的 BLAS 线程数，可用环境变量覆盖 |
| `USE_TQDM` | 默认开；`OPTIMIZE_NO_TQDM=1` 关进度条 |
| `USE_COPT` | `False` 时仅用 SciPy SLSQP；`True` 且已安装 `coptpy` 时走 `optimize_with_copt` |
| `USE_RELAXED_VELOCITY` / `VELOCITY_ANGLE_TOL` | 松弛速度约束（难收敛时试用） |

---

## 3. 主要函数与数据流

| 函数 | 作用 |
|------|------|
| `_load_search_results` | `json.load` 全文件（大文件可能慢；见性能任务） |
| `_initial_guess_from_search` | 由记录中的 `alpha`、`transfer_time`、`min_distance_orbit_idx` 构造 `NLPOptimizationVariables`；`t_ins` 取 RO `times[i]` |
| `_t_ins_bounds` | `t_ins` 盒约束 \([t_0,\, t_0+T_{ro}]\) |
| `_build_dynamics` | `CR3BP_System` + `CR3BP_Dynamics`，`rtol/atol=1e-12`，`max_step=DT` |
| `_optimize_one_case` | 构造 `DROTRONLPOptimizer`，设撞星半径与 `kwargs_opt`，调用 `optimize()` 或 `optimize_with_copt` |
| `_pack_nlp_task` | 将 DRO/RO 的 `states/times/period` 与标量参数打成 tuple，供多进程 |
| `_nlp_worker_packed` | **模块级**子进程入口：重建 `Orbit`、动力学，调用 `_optimize_one_case`（与 `transfer_search` 的 packed worker 模式一致） |
| `_worker_run_thread` | 线程池入口：共享主进程已加载的轨道与动力学 |
| `_serialize_nlp_result` | 将 `NLPOptimizationResult` 转为 JSON 可序列化字典 |
| `main` | 加载→筛选→加载轨道→串行或并行执行→写 `optimization_results_*.json` |

---

## 4. 并行策略

- **`N_WORKERS == 1`**：单进程 for 循环，`tqdm` 在 stderr。
- **`N_WORKERS > 1` 且 `PARALLEL_BACKEND="processes"`**（默认）：
  - `ProcessPoolExecutor(max_workers=min(n_workers_req, n_tasks))`
  - 提交前调用 `_apply_blas_env_for_child_processes`（`OMP_NUM_THREADS` 等），避免多进程 × 多线程 BLAS 过度抢占。
  - 每任务 `submit(_nlp_worker_packed, _pack_nlp_task(...))`。
- **`PARALLEL_BACKEND="threads"`**：`ThreadPoolExecutor`，共享主进程 `dro_orbit/ro_orbit/system/dynamics`，**不**经 packed 重建。

---

## 5. 环境变量（与代码一致）

| 变量 | 作用 |
|------|------|
| `OPTIMIZE_NO_TQDM` | 设为 `1` / `true` / `yes` 关闭 tqdm |
| `OPTIMIZE_BLAS_THREADS_PER_WORKER` | 覆盖 `LIMIT_BLAS_THREADS_PER_WORKER`（仅多进程路径有意义） |

---

## 6. 输出 JSON 结构（概要）

- 根键 `meta`：含 `search_results_file`、`dro_file`、`ro_file`、`alpha_range`、`max_transfer_time`、`nlp_solver`、`use_relaxed_velocity`、`parallel_backend`、`n_workers_requested`、`blas_threads_per_worker`（若 `processes`）等。
- 根键 `results`：每条含 `search_index`、`search_snapshot`、`nlp`（成功时）、`error`（异常时字符串）。

---

## 7. 与网格搜索的已知差异（调试时留意）

- **搜索阶段**（`TransferSearch`）与 **NLP 阶段**（`DROTRONLPOptimizer`）对出发速度扰动的构造方式不同；网格给出的 `alpha` 作为 NLP 初值仍常用，但不必严格等同同一物理参数化。若收敛差，可检查初值与边界、或启用松弛速度约束。

---

## 目标与非目标

**目标**

- 本文档与当前 `optimize.py` / `transfer_optimization.py` **行为一致**，便于新人与 AI 定位代码。
- 下列「后续任务」以可勾选形式跟踪性能与工程质量。

**非目标（本文档不展开）**

- 论文 Fig. 8/9 的作图脚本（见 TASK-016/017 与主 plan）。
- 修改 e2m2e 公共 API 的破坏性重构（除非单独开 plan）。

---

## 任务清单（按推荐顺序）

### Phase 1 — 性能与正确性基线

- [ ] 在代表性数据上运行 `python scripts/transfer/optimize.py`（可先 `MAX_CASES=1`），确认能写出 `optimization_results_*.json` 且无异常栈。
- [ ] 对单条 NLP 使用 `cProfile` 或 IDE 采样，记录 `DROTRONLPOptimizer.objective_function` / `constraint_*` / `dynamics.propagate` 占比（入口：`e2m2e/transfer/transfer_optimization.py`）。
- [ ] 核对 `search_results` 与 `DRO_FILE`/`RO_FILE` 是否来自同一套网格配置（`ALPHA_*`、`MAX_TRANSFER_TIME`）。

### Phase 2 — 减算与优化（需 Phase 1 数据支撑）

- [ ] 根据剖析结果，评估减少 `forward_integrate` 的 `t_eval` 密度、缓存同一点重复积分等（**先测量再改**）。
- [ ] 若 `json.load` 全量加载过大，评估可行解预过滤文件或流式方案（改动前在 issue/plan 中记结论）。
- [ ] 可选：将 `LIMIT_BLAS_THREADS_PER_WORKER` 与 `cpu_count`、任务数关系写入运行说明或脚本注释。

### Phase 3 — 文档与交付

- [ ] 若行为稳定，将本文件 `状态` 改为 `done`，并在 `plan/feature-orbit-transfer-replication-1.md` 的「下一步」中勾掉对应项或指向本清单。

---

## 验证与完成标准

- [ ] `optimize.py` 在 `N_WORKERS=1` 与 `PARALLEL_BACKEND=processes` 下均能完成至少一条可行解优化并写出合法 JSON。
- [ ] `meta.nlp_solver` 与 `USE_COPT` 设定一致；`processes` 时 `blas_threads_per_worker` 非空。

---

## 风险与依赖

- **依赖**：可编辑安装 `e2m2e`；`requirements.txt` 含 `tqdm`；`coptpy` 仅当 `USE_COPT=True` 时需要。
- **风险**：大 `search_results` 全量 `json.load` 内存与耗时；NLP 不收敛时需调边界或松弛约束。

---

## 进展日志（可选）

| 日期 | 说明 |
|------|------|
| 2026-03-26 | 初版文档，与 `optimize.py` 当前实现对齐 |
