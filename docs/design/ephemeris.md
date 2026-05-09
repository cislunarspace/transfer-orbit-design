---
sidebar_position: 6
---

# 星历修正

CR3BP 模型下的轨道设计完成后，需要将结果转换到高精度星历模型进行真实场景验证。

## 必要性

CR3BP 是理想化的圆型限制性三体模型，忽略了：
- 太阳引力摄动
- 月球轨道偏心率
- 真实行星位置（星历）

星历修正将 CR3BP 转移结果映射到基于 DE440/DE438 星历的 N 体模型。

## 方法一：多重打靶法

直接以星历动力学进行差分修正。

**工作流**：
1. 加载 CR3BP 轨道
2. 均匀采样生成 patch points
3. 坐标转换：synodic → J2000
4. 多重打靶差分修正
5. 验证位置连续性

**缺点**：直接从 λ=1 开始修正，初值敏感，收敛成功率低。

## 方法二：同伦法

通过分阶段引入太阳引力，提高收敛成功率。

**同伦建模**：
```
λ=0: 仅 Earth + Moon（接近 CRTBP）
λ=1: Earth + Moon + Sun（完整星历）
a(r,t,λ) = Σ_base a_b + λ · Σ_perturbation a_p
```

**工作流**：
1. Phase 1 — λ=0，E+M only，多重打靶修正
2. Phase 2 — λ: 0→1，自然延拓逐步引入 Sun 引力
3. 验证连续性

**优势**：收敛成功率更高，计算效率更好。

## 方法三：对比

`compare_ephemeris_methods.py` 同时运行两种方法，对比：
- 收敛性
- 迭代次数
- 运行时间
- 残差收敛曲线
- 轨迹质量

## 依赖

- SPICE 内核：`de440.bsp`（或 `de435.bsp`）、`naif0012.tls`
- 放置于 `e2m2e/kernels/` 或设置 `SPICE_KERNEL_DIR` 环境变量

## 脚本

```bash
# 多重打靶法
uv run python -m tod.pipelines.ephemeris.correct.correct_dro_to_ephemeris

# 同伦法
uv run python -m tod.pipelines.ephemeris.correct.homotopy_dro_to_ephemeris

# 方法对比
uv run python -m tod.pipelines.ephemeris.compare.compare_ephemeris_methods

# 可视化
uv run python -m tod.pipelines.ephemeris.plot.plot_ephemeris_correction
```
