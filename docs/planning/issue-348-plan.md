# Issue #348 实施方案：轨道保持（control_orbit）：算法层直调 + ephemeris Artifact

> 审查用。确认无误后开始实施。关联 issue：#348；拆自 #340。

## 0. 调研结论（对 issue 正文的修正/细化）

发 issue 后又核实了两处底层事实，方案据此收紧：

1. **issue 风险 #1（坐标系）已化解**：`_build_controlled_ephemeris`（`e2m2e/algorithm/station_keeping/monte_carlo.py:916-963`）**填充了 `synodic_position`**（`:962`），且约定为地心归一加 μ 平移的会合系坐标（`:921-922, 937-938`），与 `design_orbit` 的 `cr3bp_orbit.states` 同系。画布直接用 `synodic_position` 渲染即可，**无需 GCRS→会合系转换**。DTO 的 `controlled_states` 取 `synodic_position`，而非 `position_km`（GCRS）。

2. **control_orbit 对入参 EphemerisTable 的字段依赖**（决定阶段 0 存什么）：算法层 `control_orbit` → `NominalOrbit(ephemeris, spice)` → `monte_carlo`：
   - UTC 分量 `year/month/day/hour/minute/second`（`monte_carlo.py:74-78` `_utc_iso` + `:88-89` `spice.utc_to_et`）
   - `position_km` + `velocity_mps`（`monte_carlo.py:96-97`）
   - 不直接用 `synodic_position` / `times_jd_tdb`（输入侧）

   阶段 0 仍按 NPZ 全字段保存实现（含 `synodic_position` / `times_jd_tdb`），原因：① design_orbit 的 `result.ephemeris` 本就完整填充，全存零成本；② 全存才能无损重建 `EphemerisTable`，不依赖字段裁剪的正确性。

## 1. 架构约束与设计决策

### 1.1 分层约束（来自 architecture.md 硬规则）

- `src/view/` 不直接 import e2m2e，`EphemerisTable` 重建在 `FacadeBridge` 内完成，Worker/View 只传 dict / DTO。
- `src/engine/` 直调 e2m2e 算法层（ADR 0011），不经 Facade 门面。
- 结果落盘 `output/`，discovery 可恢复（ADR 0008）。

### 1.2 关键决策

| # | 决策点 | 选择 | 理由 |
|---|---|---|---|
| D1 | control_orbit 调用路径 | 直调 `algorithm.station_keeping.control_orbit` | ADR 0011；Facade `ControlOrbitResponse` 丢 `controlled_ephemeris`，无法可视化 |
| D2 | input_ephemeris 来源 | 选中 orbit Artifact 的 `extra["ephemeris"]`（NPZ 全字段）重建 `EphemerisTable` | `OrbitDesignResult.ephemeris` 已含 GCRS 星历；`controller.py:2-4` 明确输入是 design_orbit 产物 |
| D3 | ephemeris NPZ 存储 | 全字段（year/month/day/hour/minute/second/position_km/velocity_mps/synodic_position/times_jd_tdb） | control_orbit 依赖 UTC 分量 + position/velocity；完整重建最稳，免字段裁剪 |
| D4 | 受控星历可视化数据 | `controlled_ephemeris.synodic_position`（会合系） | `_build_controlled_ephemeris:962` 已填，与 design_orbit 同系，画布零改动 |
| D5 | `input_ephemeris` 字段隐藏 | main_window 在 `_build_tool_params` 后剔除控件 | 局部改动；不动 e2m2e / params_panel（跨仓库改 `Field(json_schema_extra={"hidden": True})` 收益不抵成本） |
| D6 | 触发方式 | 工具选择器 + 当前选中 orbit Artifact | 复用选工具、填参数、运行的范式；独立于 #340 右键菜单 |
| D7 | `_on_run` 重构 | 按 `tool_key` dispatch 到 `_run_design_orbit` / `_run_control_orbit` | 现硬编码 `OrbitDesignWorker`，新增工具必须泛化 |
| D8 | control 结果落盘 | 新增 `save_control_result`（独立函数） | control DTO 与 design DTO 字段差异大，`save_artifact` dispatch 反而绕；两者并列清晰 |
| D9 | 标量结果展示 | 日志面板（总 Δv / 失败样本数 / 机动次数） | ADR 0010 内嵌优先，不弹窗 |
| D10 | GUI 默认参数 | `num_monte_carlo=2`（Facade 默认 5） | 蒙特卡洛耗时远长于 design_orbit，GUI 首版求可跑通 |

## 2. 文件变更清单

| 文件 | 动作 | 行数估算 |
|---|---|---|
| `src/engine/facade_bridge.py` | 修改：`OrbitDesignResultData` 加 ephemeris 字段；`design_orbit` 提取 ephemeris；新增 `ControlResultData` + `control_orbit` 方法；`TOOL_REGISTRY` 激活 control_orbit | +115 |
| `src/engine/persistence.py` | 修改：`save_artifact` NPZ 增存 ephemeris；`load_artifact_arrays` 加载 ephemeris 到 `extra`；新增 `save_control_result` | +95 |
| `src/engine/workers.py` | 修改：新增 `ControlOrbitWorker` | +55 |
| `src/app/main_window.py` | 修改：`_on_run` dispatch；新增 `_run_control_orbit` / `_on_control_finished` / `_selected_orbit_artifact`；`_build_tool_params` 隐藏 input_ephemeris；`_on_design_finished` 落盘 ephemeris | +110 |
| `tests/engine/test_facade_bridge_control.py` | 新增 | ~130 |
| `tests/engine/test_persistence_ephemeris.py` | 新增 | ~90 |
| `tests/app/test_main_window_control.py` | 新增 | ~110 |

不动：`src/model/`（`Artifact.extra` 已是 dict，足以装 ephemeris；`artifact_type` 已支持 `"ephemeris"`）、`src/view/`（CanvasState + render 已可渲染任意 state_data，零改动）、`src/model/discovery.py`（NPZ 懒加载，discovery 不读 NPZ）。

## 3. 详细设计

### 3.1 `src/engine/facade_bridge.py`

#### 3.1.1 `OrbitDesignResultData` 增字段

```python
@dataclass
class OrbitDesignResultData:
    # ... 现有字段 ...
    mu: float | None = None
    # 新增：design_orbit 产出的 GCRS 星历（control_orbit 的标准输入）。
    # None 表示算法层未返回 ephemeris（理论上不会，defensive）。
    ephemeris: dict | None = None  # {year, month, ..., times_jd_tdb}，值均为 ndarray
```

`design_orbit()` 提取（在现有 return 块前）：

```python
eph = result.ephemeris
ephemeris_dict = None
if eph is not None:
    ephemeris_dict = {
        "year": np.asarray(eph.year),
        "month": np.asarray(eph.month),
        "day": np.asarray(eph.day),
        "hour": np.asarray(eph.hour),
        "minute": np.asarray(eph.minute),
        "second": np.asarray(eph.second),
        "position_km": np.asarray(eph.position_km),
        "velocity_mps": np.asarray(eph.velocity_mps),
        "synodic_position": np.asarray(eph.synodic_position),
        "times_jd_tdb": np.asarray(eph.times_jd_tdb) if eph.times_jd_tdb is not None else None,
    }
# return OrbitDesignResultData(..., ephemeris=ephemeris_dict)
```

#### 3.1.2 新增 `ControlResultData`

```python
@dataclass
class ControlResultData:
    """跨线程传递的轨道保持结果 DTO。纯数据，不含 e2m2e 对象引用。"""

    num_failed: int
    sk_statistic_rows: Any       # np.ndarray (n, k)，m/s；k=3 无角动量，k>=4 含
    maneuvers_mjd_tdb: Any       # np.ndarray (n,)
    maneuvers_delta_v_mps: Any   # np.ndarray (n,)，m/s
    controlled_states: Any       # np.ndarray (n, 6)：synodic_position (n,3) + 零速度列；全失败时 None
    controlled_times: Any        # np.ndarray (n,)：arange 索引（画布不依赖物理时间）；None 若无星历
    mu: float | None = None
```

> `controlled_states` 取 `synodic_position`（会合系，见 D4），速度列补零以满足 `Artifact.state_data` 的 (n,6) 约定；画布 `_draw_3d_orbits` 只用 `[:,:3]`，补零不影响渲染。`controlled_times` 存 `np.arange(n)`，画布渲染不依赖 times 物理值；若后续需要时间轴，再从 UTC 分量重建 JD_TDB。

#### 3.1.3 新增 `FacadeBridge.control_orbit`

```python
def control_orbit(
    self, ephemeris_data: dict, source_mu: float | None, **params: Any
) -> ControlResultData:
    """调用 e2m2e.algorithm.station_keeping.control_orbit，返回跨线程 DTO。

    Args:
        ephemeris_data: 来自 orbit Artifact 的 extra["ephemeris"]，
            含重建 EphemerisTable 所需的全字段 ndarray。
        source_mu: 源 orbit Artifact 的 CR3BP 质量比（extra["mu"]）。
            ControlOrbitResult 不暴露 mu，受控星历画地月标注所需，
            由调用方注入，直接写入 DTO（见 5.1）。
        **params: ControlOrbitRequest 的标量字段（control_mode 等），
            由参数面板收集。input_ephemeris 不在其中（由本方法注入）。
    """
    from e2m2e.algorithm.station_keeping import control_orbit as _control
    from e2m2e.data.types import EphemerisTable

    from src.engine.exceptions import translate_exception

    eph = EphemerisTable(**{
        k: v for k, v in ephemeris_data.items()
        if v is not None or k in {"raw_text"}  # times_jd_tdb 可为 None，走默认
    })
    params.setdefault("kernel_dir", self._kernel_dir)
    try:
        result = _control(eph, **params)
    except Exception as e:
        raise translate_exception(e) from e

    controlled = result.controlled_ephemeris
    if controlled is not None and controlled.synodic_position is not None:
        n = len(controlled)
        states = np.zeros((n, 6))
        states[:, :3] = controlled.synodic_position
        times = np.arange(n)
    else:
        states = None
        times = None

    mu = source_mu  # 由调用方从源 Artifact extra["mu"] 注入（ControlOrbitResult 不暴露 mu，见 5.1）

    return ControlResultData(
        num_failed=result.num_failed,
        sk_statistic_rows=np.asarray(result.sk_statistic.rows),
        maneuvers_mjd_tdb=np.asarray(result.maneuvers.mjd_tdb),
        maneuvers_delta_v_mps=np.asarray(result.maneuvers.delta_v_mps),
        controlled_states=states,
        controlled_times=times,
        mu=mu,
    )
```

> `EphemerisTable(**...)` 跳过值为 None 的 `times_jd_tdb`（让 dataclass 默认 `None` 生效）。`raw_text` 始终走默认空串，不存不传。

#### 3.1.4 `TOOL_REGISTRY` 激活

```python
"control_orbit": ToolSpec(
    request_model=ControlOrbitRequest,
    facade_method="control_orbit",
    label="轨道保持",
    enabled=True,   # 原 False → True
),
```

### 3.2 `src/engine/persistence.py`

#### 3.2.1 `save_artifact` NPZ 增存 ephemeris

```python
npz_payload = {
    "states": result_data.states,
    "times": result_data.times,
}
if result_data.ephemeris is not None:
    for k, v in result_data.ephemeris.items():
        if v is not None:
            npz_payload[f"eph_{k}"] = v
np.savez_compressed(npz_path, **npz_payload)
```

JSON 元数据加一行标记，供 discovery/load 判断 NPZ 是否含 ephemeris：

```python
"has_ephemeris": result_data.ephemeris is not None,
```

#### 3.2.2 `load_artifact_arrays` 加载 ephemeris

在现有 `states`/`times` 加载后追加：

```python
eph_keys = ("year", "month", "day", "hour", "minute", "second",
            "position_km", "velocity_mps", "synodic_position", "times_jd_tdb")
eph: dict = {}
for k in eph_keys:
    arr_key = f"eph_{k}"
    if arr_key in data:
        eph[k] = data[arr_key]
if eph:
    artifact.extra.setdefault("ephemeris", eph)
```

向后兼容：旧 NPZ 无 `eph_*` 键 → `extra["ephemeris"]` 不设置 → control_orbit 前置校验拦截。

#### 3.2.3 新增 `save_control_result`

```python
def save_control_result(
    result_data: ControlResultData,
    output_dir: Path,
) -> tuple[Path, Path]:
    """将轨道保持结果写入 output/ephemeris/，返回 (json_path, npz_path)。

    文件名 orbit_ephemeris_<ts>，与 discovery._EPHEMERIS_RE 兼容。
    """
    output_dir = Path(output_dir)
    eph_dir = output_dir / "ephemeris"
    eph_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    stem = f"orbit_ephemeris_{ts}"
    json_path = eph_dir / f"{stem}.json"
    npz_path = eph_dir / f"{stem}.npz"

    total_dv = float(np.sum(result_data.maneuvers_delta_v_mps))
    if result_data.controlled_states is not None:
        np.savez_compressed(
            npz_path,
            states=result_data.controlled_states,
            times=result_data.controlled_times,
        )

    meta = {
        "artifact_type": "ephemeris",
        "source_tool": "control_orbit",
        "num_failed": result_data.num_failed,
        "total_delta_v_mps": total_dv,
        "n_maneuvers": int(len(result_data.maneuvers_mjd_tdb)),
        "mu": result_data.mu,
        "states_shape": list(result_data.controlled_states.shape)
        if result_data.controlled_states is not None else None,
        "arrays_file": npz_path.name if result_data.controlled_states is not None else None,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, npz_path
```

### 3.3 `src/engine/workers.py`

```python
class ControlOrbitWorker(QThread):
    """后台执行 e2m2e 轨道保持（蒙特卡洛仿真）。

    Signals:
        log(str):                       进度/信息日志。
        finished(ControlResultData):    成功结果。
        error(str):                     错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        ephemeris_data: dict,
        params: dict[str, Any],
        source_mu: float | None,
        kernel_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ephemeris_data = ephemeris_data
        self._params = params
        self._source_mu = source_mu
        self._kernel_dir = kernel_dir

    def run(self) -> None:
        try:
            self.log.emit("开始轨道保持仿真...")
            self.log.emit(f"参数: {self._params}")
            bridge = FacadeBridge(kernel_dir=self._kernel_dir)
            data = bridge.control_orbit(
                ephemeris_data=self._ephemeris_data,
                source_mu=self._source_mu,
                **self._params,
            )
            total_dv = float(np.sum(data.maneuvers_delta_v_mps))
            self.log.emit(
                f"保持完成: 总Δv={total_dv:.2f} m/s, "
                f"失败 {data.num_failed} 样本, "
                f"{len(data.maneuvers_mjd_tdb)} 次机动"
            )
            self.finished.emit(data)
        except OrbitError as e:
            self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            self.error.emit(f"[UNKNOWN_ERROR] {e}")
```

> `ephemeris_data` 是 dict（值全为 ndarray），跨线程安全（ndarray 引用传递，Worker 只读）。

### 3.4 `src/app/main_window.py`

#### 3.4.1 import 补充

```python
from src.engine.facade_bridge import (
    TOOL_REGISTRY, ControlResultData, OrbitDesignResultData, ToolSpec,
)
from src.engine.persistence import load_artifact_arrays, save_artifact, save_control_result
from src.engine.workers import ControlOrbitWorker, OrbitDesignWorker
```

#### 3.4.2 `_on_run` 重构为 dispatch（D7）

```python
def _on_run(self) -> None:
    tool_key = self._current_tool_key
    spec = TOOL_REGISTRY.get(tool_key) if tool_key else None
    if spec is None or not spec.enabled or spec.request_model is None:
        return
    if tool_key == "design_orbit":
        self._run_design_orbit()
    elif tool_key == "control_orbit":
        self._run_control_orbit()
```

把现有 `_on_run` 的 design_orbit 主体（取 orbit_type、collect_params、起 Worker、连信号）原样移入 `_run_design_orbit`，行为不变。

#### 3.4.3 `_run_control_orbit`

```python
def _run_control_orbit(self) -> None:
    source = self._selected_orbit_artifact()
    if source is None:
        self._status_bar.showMessage("请先选中一条轨道 Artifact", _STATUS_MSG_TIMEOUT_MS)
        return
    ephemeris_data = source.extra.get("ephemeris")
    if not ephemeris_data:
        self._status_bar.showMessage("该 Artifact 无星历数据，需重新设计", _STATUS_MSG_TIMEOUT_MS)
        return

    spec = TOOL_REGISTRY["control_orbit"]
    params = collect_params(self._param_widgets, spec.request_model)
    params.pop("input_ephemeris", None)  # 防御：理论上已隐藏

    kernel_dir = self._detect_kernel_dir() or None
    self._log.clear()
    self._log.append_log(f"轨道保持: 源 {source.label}")
    self._status_bar.showMessage("正在仿真轨道保持（蒙特卡洛）...")
    self._run_btn.setEnabled(False)
    self._run_btn.setText("运行中...")

    self._worker = ControlOrbitWorker(
        ephemeris_data=ephemeris_data,
        params=params,
        source_mu=source.extra.get("mu"),
        kernel_dir=kernel_dir,
        parent=self,
    )
    self._worker.log.connect(self._on_worker_log)
    self._worker.finished.connect(self._on_control_finished)
    self._worker.error.connect(self._on_control_error)
    self._worker.start()


def _selected_orbit_artifact(self) -> Artifact | None:
    """返回当前选中的单个 orbit 类型 Artifact，否则 None。"""
    if len(self._selected_artifact_ids) != 1:
        return None
    a = self._project.get_by_id(self._selected_artifact_ids[0])
    if a is None or a.artifact_type != "orbit":
        return None
    return a
```

#### 3.4.4 `_build_tool_params` 隐藏 input_ephemeris（D5）

在 `_build_tool_params` 末尾（`layout.addStretch()` 前）追加：

```python
if tool_key == "control_orbit" and "input_ephemeris" in self._param_widgets:
    old = self._param_widgets.pop("input_ephemeris")
    # 同时移除其上方对应的 QLabel（前一轮循环加的）
    self._remove_widget_and_label(old)
```

新增辅助：

```python
def _remove_widget_and_label(self, widget: QWidget) -> None:
    """从参数容器布局移除指定控件及其前置 QLabel。"""
    layout = self._param_container_layout
    if layout is None:
        widget.setParent(None)
        return
    target_index = -1
    for i in range(layout.count()):
        if layout.itemAt(i).widget() is widget:
            target_index = i
            break
    if target_index > 0:
        prev = layout.itemAt(target_index - 1).widget()
        if isinstance(prev, QLabel):
            prev.setParent(None)
    widget.setParent(None)
```

#### 3.4.5 `_on_design_finished` 落盘 ephemeris（D2 配套）

现有 `_on_design_finished` 的 `save_artifact` 调用不变（NPZ 内部已增存 ephemeris）；`extra` dict 增补一行（让内存 Artifact 立即可用于 control_orbit，不必等懒加载）：

```python
extra={
    "cr3bp_jacobi": result.cr3bp_jacobi,
    "mu": result.mu,
    "epoch_utc": result.epoch_utc,
    "correction_converged": result.correction_converged,
    "correction_iterations": result.correction_iterations,
    "arrays_file": npz_name,
    "ephemeris": result.ephemeris,   # 新增：内存直通，control_orbit 即可用
},
```

#### 3.4.6 `_on_control_finished` / `_on_control_error`

```python
def _on_control_finished(self, result: ControlResultData) -> None:
    self._run_btn.setEnabled(True)
    self._run_btn.setText("运行")

    json_path: Path | None = None
    try:
        json_path, _ = save_control_result(result, OUTPUT_DIR)
        self._log.append_log(f"结果已保存: {json_path.name}")
    except Exception as exc:  # noqa: BLE001
        self._log.append_log(f"持久化失败: {exc}（结果仅保留在内存中）")
        self._status_bar.showMessage("持久化失败", _STATUS_MSG_TIMEOUT_MS)

    total_dv = float(np.sum(result.maneuvers_delta_v_mps))
    artifact = Artifact(
        artifact_type="ephemeris",
        label=f"受控星历 (Δv={total_dv:.1f} m/s)",
        source_tool="control_orbit",
        state_data=result.controlled_states,
        times=result.controlled_times,
        output_path=json_path,
        extra={
            "mu": result.mu,
            "num_failed": result.num_failed,
            "total_delta_v_mps": total_dv,
            "n_maneuvers": int(len(result.maneuvers_mjd_tdb)),
        },
    )
    self._project.add(artifact)
    self._refresh_project_tree()

    if artifact.state_data is not None:
        self._selected_artifact_ids = [artifact.artifact_id]
        self._render_canvas()
        self._center_tabs.setCurrentIndex(0)

    self._log.append_log(
        f"轨道保持完成: 总Δv={total_dv:.2f} m/s, "
        f"失败 {result.num_failed} 样本"
    )
    self._status_bar.showMessage("轨道保持完成", _STATUS_MSG_TIMEOUT_MS)


def _on_control_error(self, error_msg: str) -> None:
    self._run_btn.setEnabled(True)
    self._run_btn.setText("运行")
    self._log.append_log(f"错误:\n{error_msg}")
    self._status_bar.showMessage("轨道保持失败", _STATUS_MSG_TIMEOUT_MS)
```

> `controlled_states` 为 None（所有样本失败）时，Artifact 仍注册但无 state_data；点击不渲染，日志已说明失败样本数。验收标准不要求全部失败也绘制图像。

## 4. 实施顺序

| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | `facade_bridge.py`：`OrbitDesignResultData.ephemeris` + `design_orbit` 提取 + `ControlResultData` + `control_orbit` 方法 + 激活 TOOL_REGISTRY | `pytest tests/engine/test_facade_bridge.py tests/engine/test_facade_bridge_control.py -v` |
| 2 | `persistence.py`：NPZ 增存 ephemeris + `load_artifact_arrays` 加载 + `save_control_result` | `pytest tests/engine/test_persistence*.py -v` |
| 3 | `workers.py`：`ControlOrbitWorker` | 步骤 5 的测试覆盖 |
| 4 | `main_window.py`：dispatch + `_run_control_orbit` + `_on_control_finished/error` + 隐藏 input_ephemeris + design 落盘 ephemeris | `pytest tests/app/test_main_window*.py -v` |
| 5 | 新增三个测试文件 | 各步对应测试 |
| 6 | 全量回归 | `pytest tests/ -v`（基线需先确认 green） |
| 7 | 手动验证 | `uv run python -m src.app.main` → 设计 DRO → 选中 → 轨道保持 → 画布渲染 + 日志 |

> **先跑基线**：开始前 `pytest tests/ -v` 确认现有全绿（memory 记录 1113+ tests green），避免把既有失败算到自己头上。

## 5. 风险与待确认

### 5.1 技术风险

- **`ControlOrbitResult` 无直接 `mu`**（已决策）：算法层 result 不暴露 `mu`。决策为**旁路注入**：`main_window._run_control_orbit` 从源 Artifact `extra["mu"]` 取，经 `ControlOrbitWorker.source_mu` → `FacadeBridge.control_orbit(source_mu=...)` → 直接写入 `ControlResultData.mu`。不依赖 `MonteCarloResult` 是否含 mu，绕开算法层不确定性。受控星历画地月标注需要 mu，源 Artifact 无 mu 时（旧 dro）由前置校验拦截。
- **`ControlOrbitRequest` 字段集是否够跑出有意义结果**（issue 风险 #4）：Facade 模型只暴露 12 个参数，算法层默认值是否能在地月 DRO 上产出合理机动序列，**需步骤 7 手动验证**。若默认摄动（球模型光压、关耦合，`controller.py:46-52`）导致结果异常，记录为后续 issue。
- **蒙特卡洛耗时**：`num_monte_carlo=2, num_controls=120` 单次仿真可能数十秒到分钟级。GUI 不做进度条（算法层无细粒度进度回调），仅日志滚动 + 按钮禁用。若体验不可接受，后续加 QProgressDialog 不定式动画。

### 5.2 范围外（明确不做）

- 右键菜单触发（#340）。
- orbit_family_generation / orbit_stability（独立阻塞）。
- `engine_layout` 等 Any 类型参数的 UI（control_mode 4-6 角动量管理），首版不暴露。
- control 结果的 SK_STATISTIC 表格化展示（首版仅日志汇总）。

## 6. 测试计划（AAA 结构）

### 6.1 `tests/engine/test_facade_bridge_control.py`

```
test_design_orbit_result_carries_ephemeris_fields
    → bridge.design_orbit(orbit_type="DRO", amplitude=40000, duration=0.5)
    → result.ephemeris 非 None，含 position_km/velocity_mps/year 等 ndarray
    （需 SPICE 内核；若无内核环境，mock design_orbit 返回带 ephemeris 的 result）

test_control_orbit_returns_control_result_dto
    → 构造 ephemeris_data（从 design_orbit 结果或 fixture）
    → bridge.control_orbit(ephemeris_data, control_mode=1, num_monte_carlo=2)
    → ControlResultData 字段齐全；controlled_states 形状 (n,6)；synodic 在前 3 列

test_control_orbit_translates_exceptions
    → mock 算法层抛 ValueError → translate → OrbitError

test_ephemeris_table_reconstruction_skips_none_times
    → ephemeris_data["times_jd_tdb"]=None
    → control_orbit 不崩（EphemerisTable 用默认 None）
```

### 6.2 `tests/engine/test_persistence_ephemeris.py`

```
test_save_artifact_npz_contains_ephemeris_arrays
    → save_artifact(result_with_ephemeris, tmp_path)
    → np.load(npz_path) 含 eph_position_km / eph_year / ...

test_save_control_result_writes_ephemeris_dir
    → save_control_result(control_result, tmp_path)
    → output/ephemeris/orbit_ephemeris_*.json 存在
    → 文件名匹配 discovery._EPHEMERIS_RE
    → JSON 含 total_delta_v_mps / n_maneuvers / num_failed

test_load_artifact_arrays_restores_ephemeris_to_extra
    → 存带 ephemeris 的 NPZ → 构造 Artifact(output_path) → load
    → artifact.extra["ephemeris"] 含 position_km 等

test_load_old_npz_without_ephemeris_no_crash
    → 仅 states/times 的旧 NPZ → load → extra 无 "ephemeris"，不崩
```

### 6.3 `tests/app/test_main_window_control.py`

```
test_control_orbit_hidden_input_ephemeris_field
    → 选 control_orbit 工具 → _build_tool_params
    → _param_widgets 不含 "input_ephemeris"

test_run_control_without_selection_shows_status
    → 无选中 → _on_run → 不启动 Worker，状态栏提示

test_run_control_with_old_artifact_without_ephemeris_blocked
    → 选中 extra 无 ephemeris 的 Artifact → 提示无星历数据

test_run_control_dispatches_control_worker
    → mock ControlOrbitWorker → 选 orbit Artifact → _on_run
    → ControlOrbitWorker 被构造（而非 OrbitDesignWorker）

test_on_control_finished_registers_ephememeris_artifact
    → 模拟 finished 信号 → Project 含 artifact_type="ephemeris"
    → 项目树 星历 分组出现
```

## 7. 验收标准映射

| 验收标准（issue #348） | 实现位置 |
|---|---|
| design_orbit Artifact 含 GCRS 星历；重启恢复 | `facade_bridge.design_orbit` 提取 + `persistence` NPZ + `load_artifact_arrays` |
| 参数面板显示 control_mode 等（无 input_ephemeris） | `main_window._build_tool_params` 隐藏字段 |
| 选中 orbit → 运行 → ephemeris Artifact 注册星历 | `_run_control_orbit` + `_on_control_finished` |
| ephemeris Artifact 点击 → 渲染画布 | `controlled_states=synodic_position` 复用 `canvas.render()` |
| 日志显示总 Δv / 失败数 / 机动次数 | `ControlOrbitWorker.run` + `_on_control_finished` |
| 未选中运行 → 提示 | `_selected_orbit_artifact` 返回 None |
| 旧 Artifact 无星历 → 禁用提示 | `_run_control_orbit` 前置校验 |
| 仿真期间按钮禁用、日志滚动 | `_run_control_orbit` 禁用 + Worker log 信号 |