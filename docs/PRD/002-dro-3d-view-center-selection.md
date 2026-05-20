# PRD: DRO 轨道族 3D 视图绘图中心选择功能

## Problem Statement

当前 `plot_dro_family.py` 脚本绘制 DRO 轨道族 3D 视图时，绘图中心固定为月球位置（旋转坐标系中 `(1-MU, 0, 0)` ≈ `(0.9879, 0, 0)`）。用户希望能够灵活选择绘图中心，以便从不同参考系观察轨道族，例如：
- 以月球为中心（当前默认行为）
- 以地球为中心（旋转坐标系原点）
- 以地月质心（EM Barycenter）为中心的坐标系原点

同时，用户希望能够调整 3D 视角（仰角和方位角）以获得最佳的观察效果。

## Solution

为 `plot_dro_family.py` 的 3D 视图功能添加以下可配置参数：

1. **绘图中心选择**：允许用户选择以月球、地球或地月质心为 3D 视图的中心点
2. **视角调整**：允许用户调整仰角（elev）和方位角（azim）以改变观察视角
3. **GUI 集成**：在 GUI 的参数面板中，当用户勾选"全局 3D 视图"时，显示这些子选项

## User Stories

1. 作为 GUI 用户，我希望在勾选"全局 3D 视图"时能看到绘图中心的下拉选项，以便选择以地球或地月质心为参考系观察 DRO 轨道族
2. 作为 GUI 用户，我希望在勾选"全局 3D 视图"时能看到仰角和方位角的可配置输入，以便调整 3D 视角获得最佳观察效果
3. 作为 GUI 用户，我希望这些 3D 视图子选项在"全局 3D 视图"未勾选时自动隐藏，以保持界面的简洁性
4. 作为命令行用户，我希望通过 `--plot-center moon|earth|emb` 参数指定绘图中心，以支持自动化脚本
5. 作为命令行用户，我希望通过 `--plot-elev` 和 `--plot-azim` 参数调整视角，以获得不同角度的视图
6. 作为科学家，我希望默认以月球为中心绘制 3D 视图，以保持与现有工作流程的一致性
7. 作为科学家，我希望能够以地月质心为中心绘制视图，以观察轨道族相对于地月系统的整体分布

## Implementation Decisions

### 1. 新增 CLI 参数

在 `script_registry.py` 中为 `plot_dro_family` 脚本添加以下参数：

- `--plot-center`：字符串类型，选项为 `moon`、`earth`、`emb`，默认值为 `moon`
- `--plot-elev`：浮点数类型，范围 0~90°，默认值为 20°
- `--plot-azim`：浮点数类型，范围 -180°~180°，默认值为 -60°

所有参数使用角度（degrees）作为显示单位。

### 2. 绘图中心坐标映射

在地月旋转坐标系（CR3BP）中，三个中心的坐标固定为：

| 选项 | 坐标 |
|------|------|
| `moon` | `(1-MU, 0, 0)` ≈ `(0.9879, 0, 0)` |
| `earth` | `(0, 0, 0)` |
| `emb` | `(MU, 0, 0)` ≈ `(0.012, 0, 0)` |

创建一个 `get_center_coordinates(center_type: str, mu: float) -> tuple[float, float, float]` 函数来处理坐标映射。

### 3. 参数解析

在 `plot_dro_family.py` 中：
- 添加 `--plot-center`、`--plot-elev`、`--plot-azim` 的 argparse 参数定义
- 在 3D 视图绘图调用时使用这些参数值

### 4. GUI 条件可见性

修改 `params_panel_mixin.py` 中的 `_setup_conditional_visibility` 方法：
- 对于 checkbox trigger，使用 `isChecked()` 替代 `bool(text.strip())`
- 当 `--plot-global-3d` 勾选时，显示 `--plot-center`、`--plot-elev`、`--plot-azim` 控件
- 当 `--plot-global-3d` 未勾选时，这些控件自动隐藏

### 5. 参数分组

新增的三个参数放在主区域（与 `--plot-global-3d` 同级），不在"高级选项"分组中。

### 6. 向后兼容

- 默认行为保持不变（`--plot-global-3d` 勾选时默认以月球为中心）
- 不勾选 3D 视图时完全不生成相关参数
- CLI 运行时如不指定新参数，使用默认值

## Testing Decisions

### 测试覆盖范围

1. **坐标映射函数测试**：
   - 验证三个中心点坐标计算正确
   - 边界情况：MU 边界值

2. **参数解析测试**：
   - 验证 argparse 正确解析 center/elev/azim 参数
   - 验证默认值生效
   - 验证非法值被拒绝

3. **GUI 可见性测试**：
   - 验证 checkbox 未勾选时子选项隐藏
   - 验证 checkbox 勾选时子选项显示
   - 验证参数值正确传递到脚本

### 现有测试参考

参考 `tests/tod/gui/test_params_panel_mixin.py` 中的 `hidden_when` 相关测试用例。

## Out of Scope

- 修改 2D 视图的绘图中心（仅针对 3D 视图）
- 添加除月球、地球、地月质心以外的自定义中心点
- 动态调整 radius 参数（目前固定为 1.5）
- 修改其他轨道族脚本（RO、Halo 等）的 3D 视图参数
- 添加极坐标或球坐标的自定义中心输入

## Further Notes

- MU（质量比）在 `tod/commons/common.py` 中定义
- 旋转坐标系中所有中心点都在 X 轴上（Y=0, Z=0）
- 当前 `FamilyPlotter.plot_family_3d` 的 `center` 参数接受 3 元组
- GUI 使用 `choice_values` 映射机制时，显示标签到 CLI 值的转换需要注意兼容性
