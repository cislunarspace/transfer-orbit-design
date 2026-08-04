# feat: Engine 层 — DTO 修正 + TOOL_REGISTRY + 持久化 + 异常翻译

## 背景

#332（已关闭）已交付 `facade_bridge.py`、`workers.py` 及 `main_window.py` 集成，实现了最小端到端链路。
本 issue 聚焦 **净新增工作**：修正 DTO 线程安全问题、补全 TOOL_REGISTRY 注册表、实现结果持久化、结构化异常翻译。

## 要构建什么

### 1. DTO 修正 — `src/engine/facade_bridge.py`

**问题**：当前 `OrbitDesignResultData.cr3bp_orbit` 持有 e2m2e `Orbit` 对象引用，违反 DTO "纯数据类，不持有 e2m2e 对象引用"的契约（`architecture.md:173`），存在跨线程安全风险。

**修正**：将 e2m2e 富对象拆解为 numpy 数组：

```python
@dataclass
class OrbitDesignResultData:
    orbit_type: str
    epoch_utc: str
    duration_day: float
    initial_state: Any           # np.ndarray (6,)
    cr3bp_jacobi: float
    states: Any                  # np.ndarray (n,6) — 从 cr3bp_orbit.states 提取
    times: Any                   # np.ndarray (n,) — 从 cr3bp_orbit.times 提取
    correction_converged: bool
    correction_iterations: int
```

### 2. TOOL_REGISTRY — `src/engine/facade_bridge.py`

**来源**：`architecture.md:282-293`、ADR 0009。

注册 4 个已实现 Facade 方法，作为参数面板自动化的数据源：

```python
@dataclass(frozen=True)
class ToolSpec:
    request_model: type | None   # Pydantic 模型（design_orbit, control_orbit 有）
    facade_method: str           # FacadeBridge 方法名
    label: str                   # UI 显示名
    enabled: bool                # 是否启用

TOOL_REGISTRY: dict[str, ToolSpec] = {
    "design_orbit":          ToolSpec(DesignOrbitRequest,          "design_orbit",          "轨道设计", True),
    "control_orbit":         ToolSpec(ControlOrbitRequest,         "control_orbit",         "轨道保持", False),
    "orbit_family_generation": ToolSpec(None,                       "generate_family",       "轨道族生成", False),
    "orbit_stability":       ToolSpec(None,                         "analyze_stability",     "稳定性分析", False),
}
```

**注意**：e2m2e 4 个 Facade 方法中，仅 `design_orbit` 和 `control_orbit` 有 Pydantic Request 模型；`orbit_family_generation` 和 `orbit_stability` 使用原始 `**params`。`enabled=False` 的工具在 UI 中显示为"即将推出"。

### 3. FacadeBridge 参数扩展 — `src/engine/facade_bridge.py`

当前 `design_orbit()` 仅转发 4 个参数（`orbit_type`, `amplitude`, `duration`, `output_step`），而 e2m2e 算法层 `design_orbit` 接受 20+ 参数。扩展为接受 `**kwargs` 直接转发，或显式桥接关键参数（`phase`, `epoch`, `correction_method`, `perilune_height` 等）。

### 4. 结果持久化 — `src/engine/persistence.py`（新文件）

**来源**：ADR 0008。

```python
def save_artifact(result_data: OrbitDesignResultData, output_dir: Path) -> Path:
    """将计算结果写入 output/dro/ 目录，返回文件路径。

    文件命名约定（与 discovery.py 分类正则兼容）：
      dro_<YYYYMMDDHHMMSS>.json

    JSON 结构：
      - 标量元数据（orbit_type, epoch_utc, jacobi, ...）
      - initial_state: list[float]
      - states_shape: [n, 6]（不存完整数组，避免 JSON 过大）
      - times_count: int
      - 大数组保存为 .npy 旁车文件（states.npy, times.npy）
    """
```

**命名约定兼容性**（与 `discovery.py` 正则对齐）：

| 子目录 | 文件名模式 | discovery 正则 |
|---|---|---|
| `output/dro/` | `dro_<timestamp>.json` | `_DRO_ORBIT_RE` |
| `output/halo/` | `halo_<type>_<ts>.json` | `_HALO_ORBIT_RE` |
| `output/ephemeris/` | `orbit_ephemeris_<ts>.json` | `_EPHEMERIS_RE` |
| `output/transfer/` | `corrected_transfer_<ts>.json` | `_TRANSFER_CORRECTED_RE` |

### 5. 异常翻译 — `src/engine/exceptions.py`（新文件）

e2m2e 算法层定义了 5 种异常：

| e2m2e 异常 | 触发场景 | 结构化错误码 | 用户友好消息 |
|---|---|---|---|
| `DesignNotConvergedError` | 星历修正不收敛 | `CORRECTION_DIVERGED` | 轨道修正未收敛，请尝试调整振幅或修正方法 |
| `ValueError` | 参数越界 | `INVALID_PARAMS` | 参数无效：{具体信息} |
| `FileNotFoundError` | SPICE 内核缺失 | `KERNEL_NOT_FOUND` | SPICE 内核未找到，请在设置中配置内核目录 |
| `NotImplementedError` | 未实现的扰动模型 | `NOT_IMPLEMENTED` | 该功能尚未实现 |
| `UnsupportedCorrectorMethodError` | 修正方法不支持 | `INVALID_CORRECTION_METHOD` | 不支持的修正方法：{method} |

```python
class OrbitError(Exception):
    def __init__(self, code: str, message: str, cause: Exception | None = None): ...

def translate_exception(e: Exception) -> OrbitError:
    """将 e2m2e 异常翻译为 OrbitError。"""
```

### 6. Worker 层更新 — `src/engine/workers.py`

用 `translate_exception()` 替换当前 `except Exception: self.error.emit(traceback.format_exc())`，发射结构化错误码 + 友好消息。

### 7. 集成测试 — `tests/engine/`

| 测试 | 覆盖目标 |
|---|---|
| `test_facade_bridge_design_orbit` | DTO 字段完整性、numpy 数组类型 |
| `test_facade_bridge_error_translation` | 5 种异常 → OrbitError 翻译 |
| `test_save_artifact_roundtrip` | save → discover 互操作性 |
| `test_tool_registry_completeness` | 4 个工具均注册、字段完整 |
| `test_design_orbit_integration` | 端到端（需 SPICE 内核） |

### 8. 参数面板自动化 — `src/view/params_panel.py`（新文件）

**来源**：ADR 0009。

从 `DesignOrbitRequest` 的 `model_fields` 自动生成 Qt 控件，替换 `main_window.py` 中的手写参数面板（40+ 行硬编码）。`main_window.py` 改为从 `TOOL_REGISTRY` 读取 `request_model` 并调用自动生成器。

**Pydantic → Qt 映射**：

| Pydantic 字段 | Qt 控件 |
|---|---|
| `float` + `ge/le` | `QDoubleSpinBox` (range=ge..le) |
| `int` + `ge/le` | `QSpinBox` (range=ge..le) |
| `str` + Literal/Enum | `QComboBox` |
| `str` 无约束 | `QLineEdit` |
| `Optional[T]` | 对应控件 + 可选复选框 |
| `Any` (如 `epoch`) | `QLineEdit` (JSON 输入) |

## 验收标准

- [ ] `OrbitDesignResultData` 不含任何 e2m2e 对象引用，所有数据为 numpy 数组或标量
- [ ] `TOOL_REGISTRY` 包含 4 个工具，字段完整
- [ ] `save_artifact()` 写 output/dro/ 目录，文件存在且可读
- [ ] save → discover 互操作：`discover_artifacts()` 能识别 `save_artifact()` 写出的文件
- [ ] 5 种 e2m2e 异常均翻译为 `OrbitError`，含结构化错误码
- [ ] Worker 层不再发射原始 traceback，改为发射 `OrbitError.code + message`
- [ ] 参数面板从 `DesignOrbitRequest` 自动生成，`main_window.py` 不再硬编码参数控件
- [ ] 集成测试通过（mock 版不要 SPICE，端到端版需 SPICE）

## 交付文件

| 文件 | 动作 | 说明 |
|---|---|---|
| `src/engine/facade_bridge.py` | 修改 | DTO 修正 + TOOL_REGISTRY + 参数扩展 |
| `src/engine/exceptions.py` | 新建 | OrbitError + translate_exception |
| `src/engine/persistence.py` | 新建 | save_artifact() |
| `src/engine/workers.py` | 修改 | 结构化异常翻译 |
| `src/engine/__init__.py` | 修改 | 导出新符号 |
| `src/view/params_panel.py` | 新建 | Pydantic 自动生成器 |
| `src/app/main_window.py` | 修改 | 接入自动参数面板 + persistence |
| `tests/engine/__init__.py` | 新建 | |
| `tests/engine/test_facade_bridge.py` | 新建 | |
| `tests/engine/test_persistence.py` | 新建 | |
| `tests/engine/test_exceptions.py` | 新建 | |
| `tests/engine/test_integration.py` | 新建 | 端到端（需 SPICE） |

## 阻塞于

- #332（✅ 已关闭 — src/ 目录结构 + 最小可运行 GUI）

## 相关 ADR

- ADR 0008：output/ 作为数据持久化源
- ADR 0009：Pydantic 自动生成参数面板
- ADR 0011：算法层直调（绕过 Facade 门面）
