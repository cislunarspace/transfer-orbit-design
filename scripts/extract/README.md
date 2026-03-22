# Orbit Extraction Scripts

本目录下的脚本用于**从已生成的轨道族中提取指定周期的轨道**。

## ⚠️ 此目录不再维护

本方法已被新工作流替代：

```
轨道族 → 手工挑选周期接近目标的样本 → 固定T微分校正 → 所需轨道
```

新方法的优势：
- 避免复杂的轨道族插值过程
- 通过微分校正直接获得精确周期轨道

## 旧脚本说明

| 脚本 | 说明 |
|------|------|
| `extract_31_dro_orbit.py` | 从 DRO 轨道族中提取 3:1 共振轨道 |
| `extract_32_dro_orbit.py` | 从 DRO 轨道族中提取 3:2 共振轨道 |
| `extract_31_ro_orbit.py` | 从 RO 轨道族中提取 3:1 共振轨道 |
| `extract_32_ro_orbit.py` | 从 RO 轨道族中提取 3:2 共振轨道 |

## 新工作流

请参考 `scripts/generate/` 生成轨道族数据，然后使用 `e2m2e` 库中的固定周期微分校正方法（`setup_2D_symmetric_x_fixed_t`）获取目标轨道。

详细说明请参阅项目计划文档 `plan/feature-orbit-transfer-replication-1.md` 中的 TASK-008 工作流。
