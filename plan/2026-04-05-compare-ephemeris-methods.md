# DRO→星历模型修正：直接法 vs 同伦法效率对比

## 目标
创建对比脚本，重新运行直接多重打靶法和同伦法，从收敛性、迭代次数、运行时间、残差收敛过程、轨迹质量五个维度进行定量对比。

## 对比维度
| 指标 | 说明 |
|------|------|
| 收敛性 | 是否达到 1e-6 km 容差 |
| 迭代次数 | 直接法总迭代 / 同伦法各步累计迭代 |
| 运行时间 | 各方法 Wall-clock time |
| 残差收敛曲线 | 迭代 vs 最大残差 (semilogy) |
| 轨迹质量 | 3 周期传播后的 3D 轨迹对比 + 位置连续性误差 |

## 任务列表
- [ ] 1. 编写 compare_ephemeris_methods.py 脚本
  - 公共初始化 (SPICE, DRO 加载, patch points, 坐标转换)
  - 直接多重打靶法运行 (带计时)
  - 同伦法运行 (带计时)
  - 控制台对比表格输出
  - 残差收敛曲线图 (PNG)
  - 轨迹对比图 (PNG, J2000, 3 周期)
  - 对比报告 JSON
- [ ] 2. 验证脚本可导入、无语法错误

## 输出文件
- `scripts/ephemeris/compare_ephemeris_methods.py`
- `output/ephemeris/residual_comparison_<ts>.png`
- `output/ephemeris/trajectory_comparison_<ts>.png`
- `output/ephemeris/methods_comparison_<ts>.json`

## 备注
- 两种方法使用完全相同的初始 patch points (来自同一 DRO 轨道)
- 直接法用 EphemerisDynamics (E+M+Sun 全力), 同伦法用 HomotopyEphemerisDynamics (逐步引入 Sun)
- 同伦法同伦路径: λ = [0.25, 0.5, 0.75, 1.0], 不收敛时减半步长重试
- 验证均使用完整星历模型 (EphemerisDynamics)
