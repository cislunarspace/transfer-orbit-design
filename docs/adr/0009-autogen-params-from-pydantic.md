# ADR 0009：从 Pydantic 模型自动生成参数面板

**状态**：已接受
**日期**：2026-08-04
**关联**：ADR 0006（e2m2e GUI 前端定位）、ADR 0005（脚本注册合并）

## 背景

旧 GUI 通过 SCRIPT_ENTRY 的 `CliParam` 声明生成参数面板。每新增一个工具需要手写 CliParam 列表。ADR 0005 合并了镜像目录，但 CliParam 仍然是手动维护的元数据。

新架构只暴露 e2m2e 的 4 个已实现 Facade 方法，每个有对应的 Pydantic Request 模型（如 `DesignOrbitRequest`），包含完整的字段类型、范围、默认值、描述信息。

## 决策

参数面板从 e2m2e Pydantic 模型**自动生成**。遍历 Request 模型的 `model_fields`，按字段类型映射为 Qt 控件。

映射规则：

| Pydantic 字段 | Qt 控件 |
|---|---|
| `float` + `ge/le` | `QDoubleSpinBox` |
| `int` + `ge/le` | `QSpinBox` |
| `str` + Literal/Enum | `QComboBox` |
| `str` 无约束 | `QLineEdit` |
| `list[float]` | 多个 `QDoubleSpinBox` |
| `Optional[T]` | 对应控件 + 可选复选框 |

## 理由

1. **零维护同步**：e2m2e 更新 Pydantic 模型后 GUI 自动反映变更，不需要手动更新参数面板。
2. **单一事实来源**：参数定义只在 e2m2e 的 `api/models.py` 中维护。
3. **ADR 0014 对齐**：e2m2e ADR 0014 已明确 GUI 参数表单从 e2m2e Pydantic 模型生成。

## 后果

### 正面

- 新增 e2m2e Facade 方法时 GUI 零改动（只需在 TOOL_REGISTRY 加一条）
- 参数校验复用 Pydantic 的验证逻辑
- 保证参数范围/默认值与 e2m2e 一致

### 负面

- 自动生成的 UI 不够精致（如振幅用滑块更直观，但自动生成的是数字框）
- 复杂字段（如 `Any` 类型的 engine_layout）需要特殊处理
- 需要实现 Pydantic → Qt 控件的映射引擎

### 后续

- 可通过 `Field(json_schema_extra={"widget": "slider"})` 扩展 Pydantic 元数据，覆盖特定字段的 UI
