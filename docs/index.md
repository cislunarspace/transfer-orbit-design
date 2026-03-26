# 转移轨道设计 - 技术文档

本文档涵盖 transfer-orbit-design 项目，该项目复现了 Cui 等人（2025）关于从月球远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移研究。

## 文档结构

### 核心文档（与脚本对应）

| 文档 | 对应脚本 | 描述 |
|------|----------|------|
| [DRO 生成](dro-generation.md) | `generate_dro_family.py`, `plot_dro_family.py` | 远距离逆行轨道族生成 |
| [RO 生成](ro-generation.md) | `generate_31_ro_family.py`, `generate_32_ro_family.py`, `plot_*_ro_family.py` | 共振轨道族生成 |
| [RRO/ARO 生成](rro-aro-generation.md) | `generate_rro_family.py`, `generate_aro_family.py`, `plot_rro_family.py`, `plot_aro_family.py` | 3D 共振轨道生成 |
| [DRO-RO 转移](dro-ro-transfer.md) | `grid_search.py`, `optimize.py`, `plot_transfer.py` | 两脉冲转移设计 |

### 算法说明

| 文档 | 描述 |
|------|------|
| [可行解判定](algorithms/feasible-candidate-criteria.md) | 网格搜索结果 `_is_feasible` 的阈值与逻辑（e2m2e 与 `grid_search` 一致） |

### 理论基础

| 文档 | 描述 |
|------|------|
| [CR3BP 理论](cr3bp-theory.md) | 圆型限制性三体问题基础 |
| [微分修正](differential-correction.md) | 周期轨道修正方法 |
| [参数延拓](continuation-method.md) | 自然/伪弧长延拓生成轨道族 |

### 参考资料

| 文档 | 描述 |
|------|------|
| [系统概述](system-overview.md) | 项目架构、依赖和安装 |
| [API 参考](api-reference.md) | e2m2e 库 API 文档 |
| [脚本参考](scripts-reference.md) | 所有脚本详细参数说明 |
| [开发指南](development-guide.md) | e2m2e 依赖管理、符号链接设置 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 建立 e2m2e 符号链接（首次 clone 后执行）
ln -s /home/desktop/codes/e2m2e/e2m2e e2m2e

# 生成 DRO 族
python scripts/generate_dro_family.py

# 生成 RO 族
python scripts/generate_31_ro_family.py
python scripts/generate_32_ro_family.py

# 可视化结果
python scripts/plot_dro_family.py
python scripts/plot_31_ro_family.py
python scripts/plot_32_ro_family.py
```

## 轨道类型

```
DRO（远距离逆行轨道）
  └── 平面轨道，围绕月球逆行运动

RO（共振轨道）
  ├── 3:1 RO（周期 6.28 TU）
  ├── 3:2 RO（周期 12.57 TU）
  └── 平面内共振

RRO/ARO（3D 共振轨道）
  ├── RRO（反射共振轨道）
  └── ARO（轴向共振轨道）
```
