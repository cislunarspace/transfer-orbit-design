# Phase 1 轨道导入优化 - 实施计划

## 1. 问题分析

### 1.1 当前问题

当前 `phase1_grid_search.py` 的数据导入流程存在问题：

```python
# 当前实现（问题代码）
dro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(dro_files[0])  # 加载整个轨道族
ro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_files[0])    # 加载整个轨道族
dro_orbit = dro_data.orbits[args.dro_index]  # 再通过索引提取单条轨道
ro_orbit = ro_data.orbits[args.ro_index]    # 再通过索引提取单条轨道
```

**问题**：
1. 加载整个 `OrbitFamily` 但只使用其中一条轨道，浪费内存
2. 数据流不清晰，需要理解 family 和 orbit 的层级关系
3. 命令行需要同时指定文件路径和轨道索引两个参数

### 1.2 期望行为

```python
# 期望实现（直接加载单条轨道）
dro_orbit = e2m2e.core.orbit.Orbit.load(dro_file)  # 直接加载单条DRO
ro_orbit = e2m2e.core.orbit.Orbit.load(ro_file)    # 直接加载单条RO
```

### 1.3 技术背景

e2m2e 库提供两个类方法：
- `Orbit.load_from_file()` - 加载单条轨道（需要特定JSON格式）
- `OrbitFamily.load_from_file()` - 加载轨道族

当前 `output/` 下的 JSON 文件是轨道族格式（包含 `orbits` 数组），而非单条轨道格式。

## 2. 解决方案

### 方案 A：扩展 Orbit.load_from_file() 支持轨道族格式（推荐）

**思路**：修改 `Orbit.load_from_file()` 使其能自动识别格式并加载单条轨道。

**优点**：
- 用户只需提供文件路径和轨道索引
- 兼容现有 JSON 文件格式
- 保持现有数据文件不变

**缺点**：
- 需要修改 e2m2e 库

### 方案 B：命令行参数改为 JSON 文件路径（单轨道格式）

**思路**：为每条轨道单独保存 JSON 文件，格式如下：

```json
{
  "states": [...],
  "times": [...],
  "metadata": {...},
  "properties": {...}
}
```

**优点**：
- 无需修改 e2m2e 库
- 数据文件更小，加载更快

**缺点**：
- 需要转换现有数据文件
- 管理更多的小文件

### 方案 C：在 phase1 脚本中添加轨道提取逻辑

**思路**：在 `phase1_grid_search.py` 中添加辅助函数，从 family JSON 中提取指定轨道。

**优点**：
- 无需修改 e2m2e 库
- 实现简单

**缺点**：
- 脚本代码复杂度增加
- 没有解决根本问题

## 3. 推荐方案实施

采用 **方案 A**：扩展 `e2m2e.core.orbit.Orbit.load_from_file()` 方法，支持：
1. 单条轨道 JSON 格式（原有功能）
2. 轨道族 JSON 格式 + 轨道索引参数（新增功能）

### 3.1 修改 e2m2e 库

**文件**: `e2m2e/e2m2e/core/orbit.py`

**修改 `Orbit.load_from_file()` 方法签名**：

```python
@classmethod
def load_from_file(
    cls,
    filename: Union[str, Path],
    system: Optional[CR3BP_System] = None,
    orbit_index: Optional[int] = None  # 新增参数
) -> Union["Orbit", "OrbitFamily"]:
    """从文件加载轨道数据
    
    参数：
    - filename: 文件名
    - system: CR3BP_System对象（可选）
    - orbit_index: 轨道索引（可选），当文件为轨道族格式时有效
    
    返回：
    - 如果提供 orbit_index：返回指定单条 Orbit
    - 如果不提供 orbit_index 且文件为单轨道格式：返回 Orbit
    - 如果不提供 orbit_index 且文件为轨道族格式：返回 OrbitFamily
    """
```

### 3.2 修改 phase1_grid_search.py

**文件**: `scripts/transfer/phase1_grid_search.py`

**修改导入部分**：

```python
# 修改前
dro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(dro_files[0])
ro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_files[0])
dro_orbit = dro_data.orbits[args.dro_index]
ro_orbit = ro_data.orbits[args.ro_index]

# 修改后（使用新增的 orbit_index 参数）
dro_orbit = e2m2e.core.orbit.Orbit.load_from_file(
    dro_files[0], 
    orbit_index=args.dro_index
)
ro_orbit = e2m2e.core.orbit.Orbit.load_from_file(
    ro_files[0], 
    orbit_index=args.ro_index
)
```

### 3.3 修改命令行参数

```python
# 修改前
parser.add_argument('--dro', type=str, required=True, help='DRO轨道数据JSON文件')
parser.add_argument('--ro', type=str, required=True, help='RO轨道数据JSON文件')
parser.add_argument('--dro-index', type=int, default=0, help='DRO轨道索引')
parser.add_argument('--ro-index', type=int, default=0, help='RO轨道索引')

# 修改后（简化参数）
parser.add_argument('--dro', type=str, required=True, help='DRO轨道JSON文件（支持单轨或族格式）')
parser.add_argument('--ro', type=str, required=True, help='RO轨道JSON文件（支持单轨或族格式）')
parser.add_argument('--dro-index', type=int, default=None, help='DRO轨道索引（族格式时必需）')
parser.add_argument('--ro-index', type=int, default=None, help='RO轨道索引（族格式时必需）')
```

## 4. 任务清单

| 任务ID | 描述 | 优先级 | 依赖 | 状态 |
|--------|------|--------|------|------|
| TASK-IMPORT-01 | 修改 `Orbit.load_from_file()` 支持 orbit_index 参数 | P0 | - | Pending |
| TASK-IMPORT-02 | 修改 `phase1_grid_search.py` 使用新接口 | P0 | TASK-IMPORT-01 | Pending |
| TASK-IMPORT-03 | 修改 `phase2_optimize.py` 使用新接口 | P0 | TASK-IMPORT-01 | Pending |
| TASK-IMPORT-04 | 修改 `plot_transfer.py` 使用新接口 | P0 | TASK-IMPORT-01 | Pending |
| TASK-IMPORT-05 | 测试完整流程 | P0 | TASK-IMPORT-02,03,04 | Pending |

## 5. 验证计划

1. 运行 `phase1_grid_search.py --dro <file> --ro <file> --dro-index 0 --ro-index 0`
2. 运行 `phase2_optimize.py` 使用 phase1 输出
3. 运行 `plot_transfer.py` 验证绘图
