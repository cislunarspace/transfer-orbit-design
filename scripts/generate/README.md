# Orbit Family Generation Scripts

本目录中的脚本用于**从已知数值轨道数据生成完整轨道族图谱**。

## 工作流程

```
已知数值轨道数据 → 种子轨道定义 → 微分修正 → 自然延拓 → 完整轨道族
```

1. **种子轨道定义**：根据文献或前期研究结果，设定初始状态向量 `[x, y, z, vx, vy, vz]`
2. **微分修正**：利用 `DifferentialCorrection` 修正种子轨道，获得精确周期轨道
3. **自然延拓**：逐步改变参数（如周期或能量），生成完整轨道族

## 脚本列表

| 脚本 | 轨道类型 | 说明 |
|------|----------|------|
| `generate_dro_family.py` | DRO (远距离逆行轨道) | 生成 DRO 轨道族 |
| `generate_31_ro_family.py` | 3:1 RO (3:1 共振轨道) | 生成 3:1 共振轨道族 |
| `generate_32_ro_family.py` | 3:2 RO (3:2 共振轨道) | 生成 3:2 共振轨道族 |
| `generate_rro_family.py` | RRO (共振远距离逆行轨道) | 生成 RRO 轨道族 |
| `generate_aro_family.py` | ARO (幅值约化轨道) | 生成 ARO 轨道族 |

## 输出

生成的轨道族数据保存在 `output/` 目录下，格式为 JSON 文件。

## 依赖

- `e2m2e` 库：CR3BP 系统与动力学模型、微分修正算法
- `scripts/utils/common.py`：共享常量（如引力参数 MU、时间单位 TU）
