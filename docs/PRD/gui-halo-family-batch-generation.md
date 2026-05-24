# PRD: 优化 Halo 轨道族生成 GUI 界面

## Problem Statement

当前 `generate_halo_family.py` 的 GUI 参数面板存在以下问题：
1. **参数顺序混乱**：技术参数（Z振幅、延拓方法等）排在概念参数（平动点、Halo类型）之前，用户难以理解操作流程
2. **批量生成不直观**：用户需要多次手动操作才能生成完整的 Halo 轨道族（跨平动点、跨类别）
3. **参数依赖关系不明确**：natural 和 pseudo_arclength 方法的参数混在一起显示，用户不清楚何时使用哪个
4. **完整族概念不清晰**：用户不了解"完整 Halo 轨道族"包含哪些组合

## Solution

通过优化 GUI 参数面板的组织方式，让用户能够一眼理解：
1. 有哪些平动点可以选择
2. 如何选择 Halo 类别
3. 如何生成完整的轨道族

### 设计决策

**参数面板布局（从上到下）：**

```
┌─────────────────────────────────────────────────────────────┐
│  平动点选择                                                   │
│  [✓L1]  [✓L2]  [✓L3]          ← 多选芯片，红色边框           │
├─────────────────────────────────────────────────────────────┤
│  Halo 类别                                                   │
│  [✓北族 (Class I)]  [✓南族 (Class II)]  ← 多选芯片           │
├─────────────────────────────────────────────────────────────┤
│  种子配置 (高级)                                              │
│  种子轨道文件: [______________] [浏览...]                     │
│  Z振幅: [0.23] DU          ← 仅 advanced=True 时显示          │
├─────────────────────────────────────────────────────────────┤
│  延拓方法: [pseudo_arclength ▼]  ← 默认 PAL                   │
│  ↓ natural 时显示：                                          │
│    Z振幅下限: [0.001] DU                                      │
│    Z振幅上限: [0.5] DU                                       │
│    Z方向步长: [0.002] DU                                      │
│  ↓ pseudo_arclength 时显示：                                  │
│    弧长步长: [0.0045]                                        │
│    负向步长: [0.009]                                         │
├─────────────────────────────────────────────────────────────┤
│  延拓方向: [positive ▼]       ← PAL 模式下隐藏               │
├─────────────────────────────────────────────────────────────┤
│                        [运行]                                │
└─────────────────────────────────────────────────────────────┘
```

**批量执行逻辑：**

当用户选择多个平动点和/或多个 Halo 类别时：
- 自动生成所有组合（如 L1北、L1南、L2北、L2南 = 4 个组合）
- 并行启动 Job（利用现有的 job_manager 并发能力）
- 每个组合输出到独立目录：`output/halo/L1_N/`、`output/halo/L1_S/` 等

## User Stories

1. 作为新用户，我希望在参数面板顶部看到平动点选择区域，这样我能快速了解可以生成哪些平动点的 Halo 轨道

2. 作为新用户，我希望在参数面板顶部看到 Halo 类别选择，这样我能快速了解有北族和南族两种选择

3. 作为用户，我希望通过勾选多个平动点和类别来批量生成轨道族，而不需要多次操作

4. 作为高级用户，我希望能够隐藏不常用的参数（如种子轨道文件、Z振幅），使界面更简洁

5. 作为用户，我希望延拓方法的参数能够根据选择自动切换显示/隐藏，这样我不会看到无关的参数

6. 作为用户，我希望每个轨道族组合输出到独立目录，便于管理和查找

7. 作为用户，我希望并行执行多个轨道族生成任务，提高效率

## Implementation Decisions

### 1. 新增 CliChipParam 控件类型

在 `tod/gui/script_registry.py` 中添加 `CliChipParam` 数据类，支持多选芯片：

```python
@dataclass(frozen=True)
class CliChipParam:
    """多选芯片参数：GUI 渲染为一组可多选的标签按钮。"""
    flag: str              # 命令行标志，如 "--libration-point"
    label: str             # UI 显示名
    options: dict[str, list[str]]  # {显示标签: [CLI值列表]}
    default: str = ""      # 默认选中的选项
```

示例：
```python
CliChipParam(
    flag="--libration-point",
    label="平动点",
    options={"L1": ["L1"], "L2": ["L2"], "L3": ["L3"]},
    default="L1"
)
```

### 2. 修改 ScriptEntry 数据结构

`ScriptEntry` 新增可选字段：

```python
@dataclass(frozen=True)
class ScriptEntry:
    # ... existing fields ...
    cli_chip_params: list[CliChipParam] = field(default_factory=list)
    supports_batch: bool = False  # 是否支持批量生成
```

### 3. 修改 CliWidgetFactory

`tod/gui/params_panel.py` 新增 `make_chip_widget` 方法：

```python
def make_chip_widget(self, chip_param: CliChipParam) -> tuple[str, QWidget]:
    """创建多选芯片控件，返回 (key, widget)。"""
    # 返回水平布局的 QWidget，包含多个 QPushButton 作为芯片
```

### 4. 修改 ParamsPanelMixin

`tod/gui/params_panel_mixin.py` 新增：
- `_add_cli_chip_param_row` 方法
- `_collect_chip_param_values` 方法
- 修改 `_on_run` 以支持收集芯片选择结果

### 5. 修改 RunMixin

`tod/gui/run_mixin.py` 新增批量执行逻辑：

```python
def _on_run(self) -> None:
    # 收集参数后，检测是否有多选芯片
    # 如果有，展开所有组合
    # 对每个组合启动一个 Job
```

### 6. 修改 generate_halo_family.py 的参数注册

`tod/gui/scripts/generates/cr3bp/halo/generate_halo_family.py`：

```python
SCRIPT_ENTRY = ScriptEntry(
    module='halo',
    name='generate_halo_family',
    description='生成 Halo 轨道族',
    script_path='tod/generates/cr3bp/halo/generate_halo_family.py',
    output_dir='output/halo',
    group_label='生成',
    supports_batch=True,  # 新增
    cli_chip_params=[
        CliChipParam(
            flag='--libration-point',
            label='平动点',
            options={'L1': ['L1'], 'L2': ['L2'], 'L3': ['L3']},
            default='L1',
        ),
        CliChipParam(
            flag='--halo-class',
            label='Halo 类别',
            options={'北族 (Class I)': ['0'], '南族 (Class II)': ['1']},
            default='北族 (Class I)',
        ),
    ],
    cli_params=[
        # 移除 n-orbits
        # 调整参数顺序
        # amplitude-z 设置 advanced=True
        # 保持 hidden_when 联动逻辑
    ],
)
```

### 7. 修改后端脚本以支持批量参数

`tod/generates/cr3bp/halo/generate_halo_family.py` 可能需要调整：
- 考虑接受逗号分隔的多值参数（如 `--libration-point L1,L2`）
- 或者依赖 GUI 前端展开组合，后端保持单值调用

## Testing Decisions

### 测试模块

1. **tod/gui/test_chip_param.py** - 测试多选芯片控件
   - 测试芯片选择/取消选择
   - 测试默认值设置
   - 测试参数收集

2. **tod/gui/test_batch_execution.py** - 测试批量执行逻辑
   - 测试多组合展开
   - 测试并行 Job 启动
   - 测试输出目录组织

3. **tod/gui/test_halo_family_params.py** - 集成测试
   - 测试完整的参数面板渲染
   - 测试参数联动（延拓方法切换）

### 测试策略

- 单元测试：测试 CliChipParam 控件的独立行为
- 集成测试：测试参数面板渲染和运行逻辑
- E2E 测试：手动验证 GUI 交互流程

## Out of Scope

1. 其他轨道族脚本（Lyapunov、DRO 等）的批量生成界面优化
2. 预设模板功能（如"一键生成完整 L1 族"）
3. 轨道族生成的进度显示和取消功能
4. 生成的轨道族自动绘图功能

## Further Notes

### 相关 Issues

- #125: Halo 轨道族延拓方法选择与 GUI/CLI 参数对齐（相关但独立）

### 依赖项

- PyQt6 的 QPushButton 用于芯片实现
- 现有的 job_manager 并发能力
- 现有的 hidden_when 联动逻辑

### 向后兼容

- 现有的 CliParam 和 ScriptEntry 接口保持不变
- 批量生成作为可选功能，默认行为不变
