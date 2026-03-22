# Orbit Family Plotting Scripts

本目录下的脚本用于**预览和展示**通过 `scripts/generate/` 生成的轨道族数据。

## 工作流程

```
generate/ 生成轨道族数据 → plot/ 可视化预览 → 定位问题轨道 → 修正后重新生成
```

轨道族生成过程中可能出现不收敛的情况，此时需要通过交互式检查工具定位具体导致不收敛的轨道点。

## 脚本列表

| 脚本 | 说明 |
|------|------|
| `plot_dro_family.py` | 预览 DRO 轨道族 |
| `plot_31_ro_family.py` | 预览 3:1 RO 轨道族 |
| `plot_32_ro_family.py` | 预览 3:2 RO 轨道族 |
| `plot_rro_family.py` | 预览 RRO 轨道族 |
| `plot_aro_family.py` | 预览 ARO 轨道族 |
| `plot_interactive_orbit_inspector.py` | **交互式逐条检查轨道形状**，用于定位不收敛的轨道点 |

## 交互式检查工具

`plot_interactive_orbit_inspector.py` 用于逐条检查各轨道的形状。当生成轨道族时出现不收敛情况，通过此文件可以：

1. 加载轨道族数据
2. 逐条查看每条轨道的形状
3. 定位具体是哪个轨道点导致延拓失败

## 依赖

- `e2m2e` 库：轨道可视化功能
- `output/` 目录下的 JSON 轨道族数据文件
