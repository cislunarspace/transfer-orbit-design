# 实现计划：scripts/ 代码重构 + GUI 分类优化 + Code Review

## 需求重述

1. 将 `scripts/transfer/` 下的文件按转移类型分组到子目录（DRO→RO, DRO→GEO, GEO→DRO, LEO→DRO）
2. 对 `scripts/dro/`、`scripts/ro/`、`scripts/halo/`、`scripts/ephemeris/`、`scripts/inspection/` 做类似整理
3. GUI 界面中按分组显示脚本
4. **重构过程中同步进行 code-review，优化注释，统一代码风格**

---

## Phase 1: 物理文件重组

### 1.1 transfer/ 子目录结构

```
scripts/transfer/
├── dro_to_ro/
│   ├── grid_search_dro_to_ro.py
│   ├── optimize_dro_to_ro.py
│   └── plot_search_results.py          ← 重命名: plot_search_results_dro_to_ro.py
│   └── plot_optimize_result.py         ← 重命名: plot_optimize_result_dro_to_ro.py
├── dro_to_geo/
│   ├── grid_search_dro_to_geo.py
│   ├── optimize_dro_to_geo.py
│   └── plot_search_results_geo.py
├── geo_to_dro/
│   ├── grid_search_geo_to_dro.py
│   ├── optimize_geo_to_dro.py
│   ├── plot_search_results_geo_to_dro.py
│   ├── plot_optimize_result_geo_to_dro.py
│   └── validate_geo_to_dro.py
└── leo_to_dro/
    ├── grid_search_leo_to_dro.py
    └── optimize_leo_to_dro.py
```

**注意**: `plot_search_results.py` 和 `plot_optimize_result.py` 是通用名，需重命名避免与 geo_to_dro 的同名文件冲突。

### 1.2 dro/ 子目录结构

```
scripts/dro/
├── generate/
│   ├── generate_31_dro_orbit.py
│   └── generate_dro_family.py
└── plot/
    └── plot_dro_family.py
```

### 1.3 ro/ 子目录结构

```
scripts/ro/
├── generate/
│   ├── generate_31_ro_orbit.py
│   ├── generate_31_ro_family.py
│   ├── generate_32_ro_family.py
│   ├── generate_aro_family.py
│   └── generate_rro_family.py
└── plot/
    ├── plot_31_ro_family.py
    ├── plot_32_ro_family.py
    ├── plot_aro_family.py
    └── plot_rro_family.py
```

### 1.4 halo/ 子目录结构

```
scripts/halo/
├── generate/
│   ├── generate_halo_orbit.py
│   └── generate_halo_family.py
└── plot/
    ├── plot_halo_orbit.py
    └── plot_halo_family.py
```

### 1.5 ephemeris/ 子目录结构

```
scripts/ephemeris/
├── correct/
│   ├── correct_dro_to_ephemeris.py
│   └── homotopy_dro_to_ephemeris.py
├── compare/
│   └── compare_ephemeris_methods.py
└── plot/
    └── plot_ephemeris_correction.py
```

### 1.6 inspection/

保持扁平结构，只有 2 个文件。

---

## Phase 2: GUI 数据结构更新

### 2.1 修改 `ScriptEntry` dataclass（script_registry.py）

新增可选字段 `group_label: str = ""`

```python
@dataclass(frozen=True)
class ScriptEntry:
    # ... 现有字段 ...
    group_label: str = ""  # 分组标签，如 "DRO→RO"、"生成"、"绘图"
```

### 2.2 更新 main_window.py

在 `_build_left_panel()` 中：
- 遍历 SCRIPTS 时，遇到 `group_label` 非空时先插入分组标题（次级 QLabel，缩进样式）
- 分组标题样式：`"padding: 4px 16px 2px 16px; color: #777; font-size: 11px;"`

### 2.3 更新 script_registry.py 中的所有 `script_path`

将每个脚本的 `script_path` 更新为新路径，并在适当位置填充 `group_label`。

示例：
```python
# 修改前
ScriptEntry("transfer", "grid_search_dro_to_ro", ...,
    "scripts/transfer/grid_search_dro_to_ro.py", ...)

# 修改后
ScriptEntry("transfer", "grid_search_dro_to_ro",
    "DRO→RO 转移轨道网格搜索",  # description
    "scripts/transfer/dro_to_ro/grid_search_dro_to_ro.py",
    group_label="DRO→RO",  # 新增
    ...)
```

### 2.4 GUI 分组标签方案

| 模块 | group_label | 说明 |
|------|-------------|------|
| Transfer | `"DRO→RO"`, `"DRO→GEO"`, `"GEO→DRO"`, `"LEO→DRO"` | 按转移类型分组 |
| DRO | `"生成"`, `"绘图"` | |
| RO | `"生成"`, `"绘图"` | |
| Halo | `"生成"`, `"绘图"` | |
| Ephemeris | `"星历修正"`, `"对比分析"`, `"绘图"` | |
| Inspection | `""`（无分组） | |

---

## Phase 3: 验证

- [ ] 所有脚本 `python scripts/...` 能正常导入依赖
- [ ] GUI 启动 `python scripts/gui/main.py` 正常
- [ ] 左面板显示分组标题，脚本按钮缩进排列
- [ ] 运行任意脚本，验证参数传递正常

---

## 风险与依赖

1. **高风险**: 文件移动后 import 路径不变（相对 import 仍通过 `scripts/` 根），但 `sys.path` 依赖 editable install
2. **中风险**: `plot_search_results.py` 和 `plot_optimize_result.py` 重命名可能影响其他引用
3. **低风险**: GUI `group_label` 渲染需要修改 main_window.py 样式

---

## Code Review & 风格统一（贯穿全阶段）

每个文件的 refactor 同步完成：
- [ ] 注释优化：中文注释清晰、无废话、无过期 TODO
- [ ] 函数/变量命名：符合项目 camelCase 惯例（常量 UPPER_SNAKE_CASE）
- [ ] 无硬编码路径：统一用 `argparse` / 环境变量 / 相对路径
- [ ] 无冗余 import
- [ ] 类型注解：public 函数签名有类型注解
- [ ] 错误处理：关键的 `try/except` 有明确用途，非 `except Exception`
- [ ] 单个文件 < 800 行（超出的需拆分）

---

## 实施顺序

1. **Phase 1a**: 完成 transfer/ 各子目录文件移动 + 重命名 + code review
2. **Phase 1b**: 完成 dro/, ro/, halo/, ephemeris/ 子目录重组 + code review
3. **Phase 1c**: 完成 inspection/ 整理
4. **Phase 2**: 更新 script_registry.py（路径 + group_label）
5. **Phase 3**: 更新 main_window.py（GUI 分组渲染）
6. **Phase 4**: 全量验证

---

## 预计工作量

- Phase 1（文件重组 + 伴随 code review）: ~60 分钟
- Phase 2（GUI 更新）: ~30 分钟
- Phase 3（验证）: ~15 分钟
- **总计约 105 分钟**

---

**WAITING FOR CONFIRMATION**: 按此计划执行？
