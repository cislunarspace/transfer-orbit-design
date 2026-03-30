# 系统概述

## 项目目的

本项目复现以下论文的研究成果：

> **Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits**  
> Shuhao Cui, Yue Wang, Ruikang Zhang, Hao Zhang, Yang Gao  
> *Journal of Guidance, Control, and Dynamics*, Vol. 48, No. 6, June 2025  
> DOI: [10.2514/1.G008582](https://doi.org/10.2514/1.G008582)

该研究设计地月系统中周期轨道之间的转移轨迹：
- **DRO（远距离逆行轨道）**：月球周围的稳定逆行轨道
- **RO（共振轨道）**：相对于月球轨道周期具有共振比（3:2、3:1）的轨道

## 目录结构

```
transfer-orbit-design/
├── docs/                    # 技术文档
├── output/
│   ├── dro/                 # 生成的 DRO 族 JSON 文件
│   ├── ro/                  # 生成的 RO/RRO/ARO 族 JSON 文件
│   ├── halo/                # 生成的 Halo 轨道族 JSON 文件
│   └── transfer/            # 转移搜索与优化结果
├── paper/                   # 参考论文（中文翻译）
├── plan/                    # 实施计划
├── scripts/
│   ├── dro/                 # DRO 轨道生成与可视化
│   ├── ro/                  # RO/RRO/ARO 轨道生成与可视化
│   ├── halo/                # Halo 轨道生成与可视化
│   ├── transfer/            # 转移设计（搜索、优化、可视化）
│   └── utils/               # 共享参数和辅助函数
├── tests/                   # 测试
├── requirements.txt
└── README.md
```

## 依赖项

| 包 | 版本 | 用途 |
|----|------|------|
| numpy | ≥2.4.0 | 数值计算 |
| scipy | ≥1.17.0 | 科学计算（ODE 积分、优化） |
| matplotlib | ≥3.10.0 | 可视化 |
| fonttools | ≥4.0.0 | 字体处理 |
| tqdm | ≥4.66 | 进度条 |
| e2m2e | (editable) | 核心轨道力学库 |

### e2m2e 库

项目依赖 e2m2e 库，提供：

| 模块 | 用途 |
|------|------|
| `e2m2e.core.system` | CR3BP 系统参数、 librations 点 |
| `e2m2e.core.dynamics` | CR3BP 运动方程、STM 积分 |
| `e2m2e.core.orbit` | `Orbit` 和 `OrbitFamily` 数据结构 |
| `e2m2e.algorithms.differential_correction` | 周期轨道修正 |
| `e2m2e.algorithms.continuation` | 自然/伪弧长延拓 |
| `e2m2e.algorithms.stability` | 单值矩阵特征值分析 |
| `e2m2e.visualization.plotting` | 2D/3D 轨道绘图 |

## 物理参数

来自论文 Table 1：

| 符号 | 值 | 描述 |
|------|-----|------|
| μ | 1.21506683×10⁻² | 地月质量比 |
| m_s | 3.28900541×10⁵ | 太阳无量纲质量 |
| ω_s | 9.25195985×10⁻¹ | 太阳无量纲角速度 |
| ρ | 3.88811143×10² | 太阳至地月质心距离 |
| DU | 384,405 km | 距离单位 |
| TU | 4.34811305 天 | 时间单位 |
| VU | 1023.23281 m/s | 速度单位 |
| T_Moon | 2π ≈ 6.283 TU | 月球轨道周期 |

## 安装

```bash
# 克隆仓库
git clone <repository-url> transfer-orbit-design
git clone <repository-url> e2m2e

# 安装依赖
pip install -r transfer-orbit-design/requirements.txt

# 以可编辑模式安装 e2m2e
pip install -e /path/to/e2m2e
```
