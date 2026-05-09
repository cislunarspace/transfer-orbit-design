---
sidebar_position: 1
---

# 转移轨道设计 - 技术文档

本项目复现 Cui 等人（2025）关于 DRO↔RO 两脉冲转移的研究，并扩展支持 DRO↔GEO、GEO↔DRO、LEO↔DRO 转移设计。

## 快速开始

```bash
uv sync
uv run python -m tod.gui.main
```

## 文档结构

### 指南（`guides/`）

| 文档 | 描述 |
|------|------|
| [安装说明](guides/installation.md) | 依赖安装 |
| [GUI 使用](guides/gui.md) | PyQt6 桌面应用使用指南 |

### 设计文档（`design/`）— 按任务阶段

| 文档 | 描述 |
|------|------|
| [基线轨道生成](design/orbits.md) | DRO / RO / Halo 轨道生成 |
| [转移设计与优化](design/transfer.md) | 4 种转移类型的搜索-优化 |
| [星历修正](design/ephemeris.md) | CR3BP → 星历模型修正 |

### 算法说明（`algorithms/`）

| 文档 | 描述 |
|------|------|
| [可行解判定](algorithms/feasible-candidate-criteria.md) | 网格搜索 `_is_feasible` 阈值与逻辑 |
| [网格搜索与轨迹优化](algorithms/grid-search-trajectory-optimization.md) | 搜索-优化两步法设计 |

### 理论基础（`theory/`）

| 文档 | 描述 |
|------|------|
| [CR3BP 理论](theory/cr3bp-theory.md) | 圆型限制性三体问题基础 |
| [微分修正](theory/differential-correction.md) | 周期轨道修正方法 |
| [参数延拓](theory/continuation-method.md) | 自然/伪弧长延拓 |

### 参考（`reference/`）

| 文档 | 描述 |
|------|------|
| [脚本参数速查](reference/scripts.md) | 所有脚本详细参数说明 |

## 轨道类型

```
DRO（远距离逆行轨道）
  ├── 2:1 DRO（周期 ~3.47 TU）
  └── 3:1 DRO（周期 ~2.09 TU）

RO（共振轨道）
  ├── 3:1 RO（周期 ~6.28 TU）
  └── 3:2 RO（周期 ~12.57 TU）

Halo 轨道（L1 / L2 点）
```
