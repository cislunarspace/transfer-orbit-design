# 转移轨道设计 - 技术文档

本文档涵盖 transfer-orbit-design 项目，该项目复现了 Cui 等人（2025）关于从月球远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移研究。

## 文档结构

| 文档 | 描述 |
|------|------|
| [系统概述](system-overview.md) | 项目架构、依赖和安装 |
| [CR3BP 理论](cr3bp-theory.md) | 圆型限制性三体问题基础 |
| [轨道生成](orbit-generation.md) | DRO 和 RO 族生成算法 |
| [微分修正](differential-correction.md) | 周期轨道修正方法 |
| [参数延拓](continuation-method.md) | 自然延拓生成轨道族 |
| [转移设计](transfer-design.md) | 两脉冲转移设计方法论 |
| [API 参考](api-reference.md) | e2m2e 库 API 文档 |
| [脚本指南](scripts-guide.md) | 生成和可视化脚本使用 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
pip install -e C:/Users/ouyangjiahong/Codes/e2m2e

# 生成 DRO 族
python scripts/generate_dro_family.py

# 生成 RO 族
python scripts/generate_ro_family.py

# 可视化结果
python scripts/plot_dro_family.py
```

## 项目状态

- ✅ 阶段一：基线轨道生成（CR3BP）
- ⬜ 阶段二：CR3BP 转移设计
- ⬜ 阶段三：BR4BP 转移设计
- ⬜ 阶段四：星历模型验证
