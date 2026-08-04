# Issue #334 实施策略

> 配套文档：`docs/planning/issue-334-revised.md`（修订后 issue 描述）

## 目录

1. [现状分析](#1-现状分析)
2. [技术决策](#2-技术决策)
3. [实施阶段](#3-实施阶段)
4. [测试策略](#4-测试策略)
5. [风险与缓解](#5-风险与缓解)
6. [后续 issue 建议](#6-后续-issue-建议)

---

## 1. 现状分析

### 已有代码（#332 交付）

| 文件 | 行数 | 状态 |
|---|---|---|
| `src/engine/facade_bridge.py` | 88 | 需修改（DTO 缺陷 + 无 TOOL_REGISTRY） |
| `src/engine/workers.py` | 62 | 需修改（异常处理粗糙） |
| `src/engine/__init__.py` | ~1 | 需更新导出 |
| `src/model/artifact.py` | 38 | 无需修改 |
| `src/model/project.py` | 52 | 无需修改 |
| `src/model/discovery.py` | 97 | 无需修改（已实现分类正则） |
| `src/view/canvas.py` | 134 | 无需修改 |
| `src/view/log_panel.py` | — | 无需修改 |
| `src/app/main_window.py` | 297 | 需修改（接入自动参数面板 + persistence） |
| `src/app/main.py` | 24 | 无需修改 |

### e2m2e API 验证结果

| 方法 | Pydantic Request | 参数数量 | FacadeBridge 当前覆盖 |
|---|---|---|---|
| `design_orbit` | ✅ `DesignOrbitRequest`（14 字段） | 20+ | 4/20 |
| `control_orbit` | ✅ `ControlOrbitRequest`（12 字段） | 12 | 未桥接 |
| `orbit_family_generation` | ❌ 原始 `**params` | 变长 | 未桥接 |
| `orbit_stability` | ❌ 原始 `**params` | 2（orbit, dynamics） | 未桥接 |

### e2m2e 异常层次

```
Exception
├── DesignNotConvergedError (RuntimeError) — 星历修正不收敛
├── ValueError — 参数越界
├── FileNotFoundError — SPICE 内核缺失
├── NotImplementedError — 未实现的扰动模型
└── UnsupportedCorrectorMethodError (ValueError) — 修正方法不支持
```

---

## 2. 技术决策

### TD-1：DTO 纯数据化

**决策**：`OrbitDesignResultData` 不含任何 e2m2e 对象引用，所有数据在 DTO 构造时从 e2m2e 对象中提取为 numpy 数组。

**理由**：
- `Orbit` 对象可能持有 SPICE 内核句柄（有状态资源），跨线程传递不安全
- view 层不应间接依赖 e2m2e 内部类型（违反分层规则）
- DTO 序列化/调试更简单

**代价**：numpy 数组通过引用传递（零拷贝），但丧失 `Orbit` 对象上的方法。这是可接受的——GUI 只需要 `states` 和 `times` 做可视化。

### TD-2：TOOL_REGISTRY 结构

**决策**：

```python
@dataclass(frozen=True)
class ToolSpec:
    request_model: type | None   # Pydantic 模型类（None = 无正式模型）
    facade_method: str           # FacadeBridge 上的方法名
    label: str                   # UI 显示名（中文）
    enabled: bool                # 是否在 UI 中启用
```

**理由**：
- `request_model` 直接对接 ADR 0009 自动参数面板生成
- `facade_method` 字符串而非函数引用，便于序列化和日志
- `frozen=True` 防止运行时意外修改注册表

**2/4 工具无 Pydantic 模型的处理**：
- `orbit_family_generation`：需定义 `FamilyGenerationParams` TypedDict（或 dataclass）作为替代
- `orbit_stability`：需定义 `StabilityAnalysisParams` TypedDict 作为替代
- 这两个工具标 `enabled=False`，后续 e2m2e 补全 Request 模型后切换

### TD-3：持久化格式

**决策**：双文件方案——元数据 JSON + numpy 旁车文件。

```
output/dro/
├── dro_20260804_153000.json      # 标量元数据 + arrays_path 指向旁车
└── dro_20260804_153000.npz       # states + times（numpy 二进制压缩）
```

**理由**：
- JSON 存标量元数据，`discover_artifacts()` 只需解析 JSON，不触发 numpy 加载
- `.npz` 存大数组，二进制压缩比 JSON 快 10-100×，文件小 5-10×
- `discovery.py` 现有逻辑不需要修改（它只读 JSON 元数据）
- 用户需要完整数据时，从 `output_path` 的同目录 `.npz` 文件加载

**替代方案（已排除）**：
- 纯 JSON（含嵌套数组）：10000×6 状态矩阵的 JSON 约 2-5 MB，解析慢
- `.npy` 旁车文件：无压缩，文件更大
- 复用 e2m2e `write_ephemeris()`：输出 DFH 格式文本，与 discovery 正则不兼容

### TD-4：异常翻译层

**决策**：在 `FacadeBridge` 内部捕获 e2m2e 异常并翻译为 `OrbitError`，Worker 层只负责发射。

```python
# FacadeBridge 内部
try:
    result = design_orbit(...)
except DesignNotConvergedError as e:
    raise OrbitError("CORRECTION_DIVERGED", "轨道修正未收敛...", cause=e) from e
except FileNotFoundError as e:
    raise OrbitError("KERNEL_NOT_FOUND", "SPICE 内核未找到...", cause=e) from e
# ...

# Worker 层
try:
    data = bridge.design_orbit(...)
except OrbitError as e:
    self.error.emit(f"[{e.code}] {e.message}")
```

**理由**：
- 翻译逻辑集中在 FacadeBridge（单一职责）
- Worker 不需要知道 e2m2e 的异常层次
- `OrbitError.code` 可用于日志分类和遥测

### TD-5：参数面板自动化范围

**决策**：本 issue 实现 `params_panel.py` 自动生成器 + `main_window.py` 接入，但仅对 `design_orbit` 生效（唯一 `enabled=True` 且有 Pydantic 模型的工具）。

**理由**：
- ADR 0009 是架构承诺，TOOL_REGISTRY 就绪后应立即兑现
- 替换手写面板可减少 `main_window.py` ~40 行硬编码
- 为后续工具（control_orbit 启用时）零成本扩展

---

## 3. 实施阶段

### Phase 1：DTO + FacadeBridge 核心修正

**文件**：`src/engine/facade_bridge.py`

**步骤**：

1. **重定义 `OrbitDesignResultData`**
   - 移除 `cr3bp_orbit: Any` 字段
   - 新增 `states: Any`（`np.ndarray (n,6)`）和 `times: Any`（`np.ndarray (n,)`）
   - 在 DTO 构造时从 `OrbitDesignResult.cr3bp_orbit` 提取

2. **新增 `ToolSpec` 数据类和 `TOOL_REGISTRY`**
   - 4 个条目，`design_orbit` enabled=True，其余 False
   - 导入 `DesignOrbitRequest`（e2m2e.api.models）

3. **扩展 `FacadeBridge.design_orbit()`**
   - 方案 A（推荐）：接受 `**kwargs`，直接转发给 `e2m2e.algorithm.design.design_orbit`
   - 方案 B：显式桥接每个参数（更类型安全但维护成本高）
   - 统一传入 `kernel_dir=self._kernel_dir`

4. **构造 DTO 时提取 numpy 数组**
   ```python
   result = design_orbit(orbit_type, **kwargs)
   return OrbitDesignResultData(
       ...
       states=result.cr3bp_orbit.states,    # np.ndarray (n,6)
       times=result.cr3bp_orbit.times,      # np.ndarray (n,)
       ...
   )
   ```

**验证**：运行现有测试（如有）确保不回归。

---

### Phase 2：异常翻译

**文件**：`src/engine/exceptions.py`（新建）

**步骤**：

1. **定义 `OrbitError`**
   ```python
   class OrbitError(Exception):
       code: str        # 结构化错误码
       message: str     # 用户友好消息
       cause: Exception | None  # 原始异常
   ```

2. **定义 `translate_exception(e: Exception) -> OrbitError`**
   - 按异常类型匹配：`DesignNotConvergedError` → `CORRECTION_DIVERGED`，等等
   - 未匹配的异常 → `UNKNOWN_ERROR` + 原始消息

3. **在 `FacadeBridge` 中集成翻译**
   - `design_orbit()` 方法 wrap try/except，调用 `translate_exception()`
   - 未来其他工具方法复用同一翻译函数

**验证**：`tests/engine/test_exceptions.py` — 每种异常一个测试用例。

---

### Phase 3：Worker 层更新

**文件**：`src/engine/workers.py`

**步骤**：

1. 导入 `OrbitError`
2. 将 `run()` 方法的 except 块改为：
   ```python
   except OrbitError as e:
       self.error.emit(f"[{e.code}] {e.message}")
   except Exception:
       self.error.emit(f"[UNKNOWN_ERROR] {traceback.format_exc()}")
   ```

**影响范围**：仅 `OrbitDesignWorker.run()` 方法，约 5 行改动。

---

### Phase 4：持久化

**文件**：`src/engine/persistence.py`（新建）

**步骤**：

1. **定义 `save_artifact(result_data, output_dir) -> Path`**
   - 参数类型：`OrbitDesignResultData`（Phase 1 修正后的 DTO）
   - 输出目录：`output_dir / "dro"`（根据 `orbit_type` 决定子目录）

2. **文件命名**：`dro_<YYYYMMDDHHMMSS>.json`（与 `_DRO_ORBIT_RE = r"^dro_\d+\.json$"` 兼容）
   - 注意：当前正则要求纯数字时间戳，不接受下划线分隔
   - 格式：`dro_20260804153000.json`（14 位数字）

3. **JSON 内容结构**：
   ```json
   {
     "orbit_type": "DRO",
     "epoch_utc": "2024-01-01T00:00:00",
     "duration_day": 365.25,
     "cr3bp_jacobi": 3.005811,
     "correction_converged": true,
     "correction_iterations": 3,
     "initial_state": [x, y, z, vx, vy, vz],
     "states_shape": [8761, 6],
     "times_count": 8761,
     "arrays_file": "dro_20260804153000.npz"
   }
   ```

4. **NPZ 旁车文件**：`np.savez_compressed(path, states=..., times=...)`
   - 与 JSON 同目录、同文件名（仅扩展名不同）

5. **子目录映射**：
   ```python
   _SUBDIR_MAP = {
       "DRO": "dro",
       "Halo": "halo",
       "NRHO": "halo",
       "Lissajous": "halo",
       "L4": "dro",
       "L5": "dro",
   }
   ```

**验证**：`tests/engine/test_persistence.py`
- `test_save_creates_json_and_npz`：验证两个文件都存在
- `test_save_json_is_valid`：JSON 可解析、字段完整
- `test_save_discover_roundtrip`：`discover_artifacts()` 能识别保存的文件

---

### Phase 5：参数面板自动化

**文件**：`src/view/params_panel.py`（新建）、`src/app/main_window.py`（修改）

**步骤**：

1. **实现 `build_params_from_model(model_class, parent) -> dict[str, QWidget]`**
   - 遍历 `model_class.model_fields`
   - 按字段类型映射为 Qt 控件（见 ADR 0009 映射表）
   - 返回 `{field_name: widget}` 字典

2. **实现 `collect_params(widgets: dict) -> dict`**
   - 遍历 widgets，按控件类型提取值
   - 返回可直接传给 `FacadeBridge.design_orbit(**params)` 的字典

3. **修改 `main_window.py`**
   - 删除 `_build_design_orbit_params()` 方法（~40 行）
   - 替换为调用 `build_params_from_model(DesignOrbitRequest, panel)`
   - `_on_run_design()` 改为调用 `collect_params(self._param_widgets)`

4. **特殊字段处理**：
   - `orbit_type`（str + Literal）→ `QComboBox`，选项从 `Literal["DRO", "Halo", ...]` 提取
   - `epoch`（Any，默认 tuple）→ `QLineEdit`（JSON 输入），或保留为默认值
   - `correction_method`（str，默认 "two_level"）→ `QComboBox`，选项 `["standard", "two_level", "homotopy"]`

**验证**：
- `tests/engine/test_params_panel.py`：生成的控件数量 = 模型字段数量
- 手动测试：启动 GUI，确认所有参数可编辑

---

### Phase 6：集成测试

**文件**：`tests/engine/test_integration.py`（新建）

| 测试 | 依赖 | 说明 |
|---|---|---|
| `test_design_orbit_dto_fields` | mock e2m2e | DTO 字段完整性 |
| `test_design_orbit_numpy_arrays` | mock e2m2e | states/times 为 ndarray |
| `test_design_orbit_error_kernel_missing` | mock e2m2e | FileNotFoundError → KERNEL_NOT_FOUND |
| `test_design_orbit_error_not_converged` | mock e2m2e | DesignNotConvergedError → CORRECTION_DIVERGED |
| `test_save_and_discover` | 实文件系统 | save → discover 互操作 |
| `test_e2e_design_orbit` | SPICE 内核 | 真实 e2m2e 调用（标记 `@pytest.mark.integration`） |

---

## 4. 测试策略

### 单元测试（不需要 SPICE）

```
tests/engine/
├── __init__.py
├── test_facade_bridge.py      # DTO 构造、TOOL_REGISTRY 完整性
├── test_exceptions.py         # 5 种异常翻译
├── test_persistence.py        # save_artifact 输出验证
├── test_params_panel.py       # Pydantic → Qt 控件映射
└── test_integration.py        # mock e2e + 真实 e2e
```

**mock 策略**：
```python
# conftest.py
@pytest.fixture
def mock_design_orbit(monkeypatch):
    """Mock e2m2e.algorithm.design.design_orbit，返回假 OrbitDesignResult。"""
    fake_result = OrbitDesignResult(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        output_step_sec=3600.0,
        initial_state=np.zeros(6),
        cr3bp_orbit=FakeOrbit(states=np.random.randn(100, 6), times=np.arange(100)),
        cr3bp_jacobi=3.0058,
        correction=FakeCorrection(converged=True, iterations=3),
        ...
    )
    monkeypatch.setattr("src.engine.facade_bridge.design_orbit", lambda *a, **kw: fake_result)
```

### 集成测试（需要 SPICE）

标记 `@pytest.mark.integration`，CI 中可选运行（SPICE 内核体积大，不纳入 CI 缓存）。

---

## 5. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| e2m2e `OrbitDesignResult` 字段变更 | 低 | DTO 构造失败 | e2m2e 自身测试覆盖；DTO 构造有单元测试 |
| `DesignOrbitRequest` 字段与算法层参数不对齐 | 低 | 自动参数面板遗漏参数 | 对比 `design_orbit` 签名和 Request 模型字段 |
| discovery 正则不匹配新文件名 | 中 | 保存的文件无法被发现 | `test_save_discover_roundtrip` 覆盖 |
| `.npz` 文件损坏导致数据丢失 | 低 | GUI 无法渲染 | JSON 中记录 `states_shape`，加载时校验 |
| Pydantic `Any` 类型字段（epoch, engine_layout） | 中 | 自动控件质量差 | `epoch` 提供 QLineEdit + JSON 验证；`engine_layout` 保留手动处理 |

---

## 6. 后续 issue 建议

| Issue | 依赖 | 说明 |
|---|---|---|
| `control_orbit` 桥接 + 启用 | #334 | TOOL_REGISTRY 中 `enabled=True`，实现 `FacadeBridge.control_orbit()` |
| `orbit_family_generation` 桥接 | #334 + e2m2e Pydantic 模型 | 等 e2m2e 补全 Request 模型 |
| `orbit_stability` 桥接 | #334 + e2m2e Pydantic 模型 | 等 e2m2e 补全 Request 模型 |
| 项目树右键菜单 | #334 | 从 TOOL_REGISTRY 生成上下文操作 |
| Discovery 增强 — 加载 numpy 数组 | #334 | `discover_artifacts()` 可选加载 .npz 旁车文件 |
| 旧代码清理 | 所有新 GUI issue 完成后 | 删除 `tod/gui/`、`tod/generates/`、`tod/scripting/` |
