# PRD: 轨道族多文件绘制功能

## Problem Statement

用户在使用轨道族绘制功能时存在以下痛点：

1. **跨文件对比困难**：Halo 轨道族数据按不同生成参数分散在多个 JSON 文件中，用户需要分别绘制再手动拼接截图进行对比
2. **缺乏批量绘图工具**：现有 `plot_halo_family.py` 仅支持单文件绘制，没有脚本支持将多个轨道族叠加在同一张图中
3. **无法精细控制绘制范围**：用户可能只想对比不同文件中轨道的某个片段，而非全部

## Solution

在 GUI 和命令行中提供多文件绘制能力：

1. **GUI 多文件选择**：用户可通过 ListWidget 添加多个 JSON 文件，每个文件独立配置绘制范围
2. **索引独立配置**：每个文件可设置 start/end/step，程序静默截断越界值
3. **统一视图绘制**：所有选中文件的轨道叠加绘制在同一张图上
4. **通用支持**：此功能基于通用架构实现，支持所有轨道族类型（Halo、DRO、Vertical、LPO 等）

## User Stories

1. 作为用户，我想要选择多个 JSON 文件并同时绘制，这样我可以在同一张图中对比不同参数的轨道族
2. 作为用户，我想要为每个文件单独设置绘制范围，这样我可以只比较轨道的某个片段
3. 作为用户，我希望在 GUI 中看到已选文件的列表并可随时增删，这样我可以灵活调整要绘制的内容
4. 作为用户，我希望在选中文件后能立即配置其索引参数，这样交互流程顺畅
5. 作为用户，我希望能用命令行一次性传入多个文件和配置，这样我可以自动化重复的绘图任务
6. 作为用户，即使我设置的索引超出文件实际轨道数量，程序也能智能处理而不是报错，这样我不会因为参数错误而中断工作流
7. 作为用户，绘制结果能自动计算统一的视图边界，这样不同范围的轨道都能完整显示
8. 作为开发者，这个功能可以复用到其他轨道族类型（DRO、Vertical、LPO 等），这样无需重复开发
9. 作为用户，我希望能同时绘制 2D 和 3D 视图，以及稳定性分析图，多文件模式下这些功能同样适用

## Implementation Decisions

### 1. 扩展 FamilyPlotOrchestrator 支持多文件

`tod/plot/family_plot_orchestrator.py` 的 `--json-file` 参数改为接受 JSON 字符串格式的数组：

```python
# CLI 调用示例
python -m tod.plot.halo.plot_halo_family \
  --json-file '[{"path": "a.json", "start": 0, "end": 10, "step": 2}, {"path": "b.json", "start": 5, "end": -1, "step": 1}]'
```

数据结构：
```python
@dataclass(frozen=True)
class MultiFileConfig:
    """多文件绘制配置项。"""
    path: str           # 文件路径
    start: int = -1    # 起始索引，-1 表示从第一条
    end: int = -1      # 结束索引，-1 表示到最后一条
    step: int = 1      # 绘制间隔
```

### 2. 新增 MultiCliParam 类型

在 `tod/gui/script_registry.py` 中新增 `MultiCliParam` 数据类：

```python
@dataclass(frozen=True)
class MultiCliParam:
    """多文件参数：GUI 渲染为文件列表控件，每项包含路径和索引配置。"""
    flag: str                              # 命令行标志
    label: str                             # UI 显示名
    file_category: str | None = None       # 文件类别过滤
    name_pattern: str | None = None       # 文件名过滤模式
    help: str = ""                        # 帮助文本
    default_unit: str | None = None        # 默认单位
```

### 3. GUI ListWidget 实现

在 `tod/gui/params_panel_mixin.py` 中新增多文件控件渲染：

- **文件列表区域**：QListWidget 显示已选文件（友好名称）
- **添加按钮**：打开 QFileDialog 多选 JSON 文件
- **删除按钮**：移除选中的文件
- **选中状态**：单击列表项时右侧显示该文件的配置面板

### 4. 右侧索引配置面板

当列表中有文件被选中时，右侧显示：

```
文件: halo_L1_N_family.json (21 条轨道)
────────────────────────────
起始索引: [0    ]  (-1 = 首条)
结束索引: [10   ]  (-1 = 末条)
绘制间隔: [2    ]  (每隔 N 条绘一条)
```

### 5. 多文件聚合绘制逻辑

`FamilyPlotOrchestrator` 扩展：

```python
def _load_multi_families(self, configs: list[MultiFileConfig]) -> tuple[OrbitFamily, list[str]]:
    """加载多个文件并聚合为一个 OrbitFamily。"""
    all_orbits: list[Orbit] = []
    family_names: list[str] = []
    for cfg in configs:
        family = OrbitFamily.load_from_file(Path(cfg.path), system)
        start, end = resolve_plot_range(cfg.start, cfg.end, len(family))
        subset = self._build_subset(family, start, end)
        all_orbits.extend(subset.orbits)
        family_names.append(Path(cfg.path).stem)
    # 返回合并后的 family 和名称列表
```

### 6. 视图边界计算

多文件时，取所有轨道的状态的 min/max 计算统一边界：

```python
def compute_multi_view_bounds(all_families: list[OrbitFamily]) -> tuple:
    """计算多家族的统一视图边界。"""
    all_states = np.vstack([orbit.states for family in all_families for orbit in family])
    return compute_view_bounds(all_states)
```

### 7. CLI 参数解析

扩展 `build_argparser` 支持多文件格式：

```python
def _parse_json_files(arg_value: str) -> list[MultiFileConfig]:
    """解析 JSON 字符串为 MultiFileConfig 列表。"""
    import json
    data = json.loads(arg_value)
    return [MultiFileConfig(**item) for item in data]
```

### 8. 脚本注册更新

`tod/gui/scripts/plot/halo/plot_halo_family.py` 使用新参数类型：

```python
SCRIPT_ENTRY = ScriptEntry(
    # ...
    cli_params=[
        MultiCliParam(
            flag='--json-file',
            label='轨道族文件',
            file_category='halo',
            name_pattern='*_family_*.json',
            help='支持多文件：点击"添加"选择多个文件，每个文件可单独配置绘制范围',
        ),
        # 移除原有的 --start, --end, --step（由 MultiCliParam 内嵌）
        # ... 其他参数
    ],
)
```

### 9. 静默截断逻辑

`resolve_plot_range` 函数保持现有行为，自动处理越界：

```python
def resolve_plot_range(start: int, end: int, n_orbits: int) -> tuple[int, int]:
    """解析 start/end，返回截断后的有效范围。"""
    last = n_orbits - 1
    s = min(start, last) if start >= 0 else 0
    e = min(end, last) if end >= 0 else last
    return (s, max(s, e))  # 确保 start <= end
```

## Testing Decisions

### 测试模块

1. **tod/plot/test_family_plot_orchestrator.py**
   - 测试多文件加载和聚合
   - 测试统一边界计算
   - 测试静默截断行为

2. **tod/gui/test_multi_cli_param.py**
   - 测试 MultiCliParam 数据结构
   - 测试 JSON 序列化/反序列化
   - 测试默认参数合并

3. **tod/gui/test_multi_file_widget.py**
   - 测试 ListWidget 添加/删除
   - 测试选中状态切换
   - 测试索引配置面板联动

### 测试策略

- 单元测试：测试 `MultiFileConfig` 和 `resolve_plot_range` 的边界行为
- 集成测试：使用临时 JSON 文件测试完整的多文件绘制流程
- 手动测试：GUI 交互流程验证

### 测试数据

使用 `output/halo/` 下的现有 JSON 文件进行测试。

## Out of Scope

1. **颜色控制**：初始版本所有轨道使用相同的 colormap（按 Jacobi 常数着色），不支持为不同文件指定不同颜色
2. **图例**：初始版本不显示多文件图例，后续可基于 family_name 添加
3. **分组绘制选项**：不支持选择性地只绘制部分文件的部分轨道
4. **保存/加载配置**：不支持保存多文件配置模板供后续复用

## Further Notes

### 扩展点

未来可依次添加：
1. 每个文件的独立颜色配置
2. 多家族图例
3. 配置模板保存/加载
4. 扩展到转移轨道（Transfer）绘图

### 相关模块

- `tod/plot/family_plot_orchestrator.py` - 核心绘制逻辑
- `tod/gui/script_registry.py` - 参数类型定义
- `tod/gui/params_panel_mixin.py` - GUI 控件渲染
- `tod/plot/halo/plot_halo_family.py` - Halo 绘图入口
- `tod/gui/scripts/plot/halo/plot_halo_family.py` - GUI 参数注册

### 向后兼容

- 单文件调用方式保持不变：`--json-file path.json` 仍然有效
- 现有 `start`/`end`/`step` 参数在单文件时行为不变
- GUI 注册使用新参数类型后自动获得多文件能力

### GitHub Issue

- #133
