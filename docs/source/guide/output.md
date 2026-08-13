# 输出与数据格式

## output/ 目录

所有工具结果统一落盘到项目根目录 `output/` 下，按工具与轨道类型分目录：

| 目录 | 产物 | 文件命名 |
|------|------|----------|
| `output/<type>/` | 轨道设计 | `<type>_<UTC时间戳>.json` + `.npz`（type 为 dro/halo/nrho/lissajous/l4/l5） |
| `output/ephemeris/` | 轨道保持 | `orbit_ephemeris_<时间戳>.json` + `.npz` |
| `output/family/` | 轨道族生成 | `family_<时间戳>.json` + `.npz` |
| `output/stability/` | 稳定性分析 | `<标签>_stability_<时间戳>.json`（仅 JSON） |

时间戳为 UTC 14 位 `YYYYMMDDHHMMSS`。启动时 GUI 扫描 `output/`，按
"目录 + 文件名前缀"识别并重建为工件；未识别文件不影响启动。

## 双文件约定

**JSON 存参数与标量统计，NPZ 存轨道数组**。JSON 的 `arrays_file` 键记录
伴随 NPZ 文件名，两文件成对出现、一起删除。

### 轨道设计

JSON：

```json
{
  "orbit_type": "DRO",
  "epoch_utc": "2024-01-01T00:00:00",
  "duration_day": 30.0,
  "cr3bp_jacobi": 3.0058,
  "mu": 0.012150585,
  "correction_converged": true,
  "correction_iterations": 3,
  "initial_state": [1.1, 0.0, 0.0, 0.0, 0.2, 0.0],
  "states_shape": [145, 6],
  "has_ephemeris": true,
  "arrays_file": "dro_20260813000102.npz"
}
```

NPZ 键：

| 键 | 形状 | 含义 |
|----|------|------|
| `states` | (n, 6) | CR3BP 周期轨道状态 |
| `times` | (n,) | CR3BP 时间（无量纲 TU） |
| `eph_year` … `eph_second` | (m,) | 星历 UTC 拆分 |
| `eph_position_km` | (m, 3) | GCRS 位置（km） |
| `eph_velocity_mps` | (m, 3) | GCRS 速度（m/s） |
| `eph_synodic_position` | (m, 3) | 会合系位置（质心归一） |
| `eph_times_et` | (m,) | 真物理时间（J2000 ET 秒） |

### 轨道保持

JSON 存 `num_failed`（失败样本数）、`total_delta_v_mps`（总速度增量）、
`n_maneuvers`（机动次数）、`mu`。NPZ 键：

| 键 | 形状 | 含义 |
|----|------|------|
| `states` | (n, 6) | 受控星历（质心归一会合系位置 + 零速度列） |
| `times` | (n,) | 物理时间（ET 秒） |
| `position_km` | (n, 3) | GCRS 惯性位置（km） |
| `times_et` | (n,) | 真物理时间（ET 秒，与 times 同源） |

全样本失败时只写 JSON（`num_failed` = 样本数），无 NPZ。

### 轨道族生成

JSON 存 `orbit_type`（Halo）、`libration_point`、`n_orbits`、`mu`。NPZ 键：

| 键 | 形状 | 含义 |
|----|------|------|
| `states` | (m, n, 6) | 一族成员状态（m 成员 × n 采样点） |
| `times` | (m, n) | 各族成员时间（TU） |
| `z0s` | (m,) | 各族成员面外振幅 |

### 稳定性分析

仅 JSON：单值矩阵、特征值（复数存 `[real, imag]`）、稳定性指数
（ν₁/ν₂/ν₃/Broucke）、稳定性分类、分岔检测与数值误差。

## 工件与文件的关系

- 每个工件对应 `output/` 下的一个 JSON（+ 伴随 NPZ）；删除工件即删除文件
  （删除前确认路径）。
- 工件可作为后续工具的输入：轨道保持以轨道工件的星历为输入，稳定性分析以
  轨道工件的 CR3BP 状态为输入。数据在内存中传递，不经过文件读写。
- 旧版本产物（如旧的 `dro_*_family_*.json` 轨道族命名）仍可被识别，但新
  产物一律使用上表命名。
