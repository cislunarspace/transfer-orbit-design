# 脚本指南

## 轨道生成脚本

### generate_dro_family.py

使用微分修正和自然延拓生成远距离逆行轨道族。

```bash
python scripts/generate_dro_family.py
```

**输出**：`output/dro/` 中的 JSON 文件

**关键参数**：
- `x0`：初始 x 位置（默认 ~0.7919）
- `vy0`：初始 y 速度（默认 ~0.5368）
- `param_range`：x0 延拓范围（0.6 到 0.8）
- `step_size`：延拓步长（默认 0.005）

### generate_ro_family.py

生成共振轨道族（3:2 和 3:1）。

```bash
python scripts/generate_ro_family.py
```

### generate_31_ro_family.py

专门生成 3:1 共振轨道族。

```bash
python scripts/generate_31_ro_family.py
```

**关键参数**：
- `x0_range`：(-1.0, -0.7)
- `period`：2π ≈ 6.283 TU

### generate_32_ro_family.py

专门生成 3:2 共振轨道族。

```bash
python scripts/generate_32_ro_family.py
```

**关键参数**：
- `x0_range`：(-1.2, -0.8)
- `period`：4π ≈ 12.566 TU

### phase1_generate_ro.py

用于初始 RO 种子识别的旧版脚本。

## 可视化脚本

### plot_dro_family.py

绘制带有 Jacobi 常数和稳定性着色的 DRO 族。

```bash
python scripts/plot_dro_family.py
```

**输出**：PNG 图表，显示：
- 整个族的 2D XY 投影
- Jacobi 常数 vs 轨道索引
- 稳定性指数 vs 轨道索引
- 种子轨道的 3D 轨迹

### plot_ro_family.py

类似地绘制 RO 族。

```bash
python scripts/plot_ro_family.py
```

## 工具脚本

### utils/params.py

物理常数（SI 单位）：

| 常数 | 值 | 单位 |
|------|-----|------|
| MU | 1.21506683e-2 | - |
| M_SUN | 3.28900541e5 | - |
| OMEGA_SUN | 9.25195985e-1 | - |
| RHO | 3.88811143e2 | - |
| DU | 3.84405e5 | km |
| TU | 4.34811305 | 天 |
| VU | 1023.23281 | m/s |
| T_MOON | 2π | TU |

### utils/common.py

共享函数：
- `ensure_output_dir()`：创建输出目录
- `get_latest_family_file()`：查找最新的输出
