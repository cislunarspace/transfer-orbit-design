# homotopy_dro_to_ephemeris.py 修复与优化

## 目标
修复 homotopy_dro_to_ephemeris.py 运行速度慢、参数错误等问题，与 correct_dro_to_ephemeris.py 的优化对齐。

## 问题诊断
| 问题 | 位置 | 影响 |
|------|------|------|
| `convert_to_j2000` 传入 `TU_SECONDS`（秒） | homotopy 第 103 行 | **严重**：tu_days 参数应传天数 `TU`，传秒会导致时间偏差 |
| `MultipleShooting` 缺少 `n_workers`/`kernel_dir` | homotopy 多处 | 单进程运行，速度慢 |
| `BODIES` 用字符串列表 | homotopy 顶部 | 与 correct 脚本不一致；直接用 `BodyName.EARTH_MOON_SUN` 更清晰 |
| `compare_ephemeris_methods.py` 有同样问题 | compare 脚本 | 同步修复 |

## 任务列表
- [x] 1. 修复 `homotopy_dro_to_ephemeris.py`：`convert_to_j2000` 参数 `TU_SECONDS` → `TU`
- [x] 2. 修复 `homotopy_dro_to_ephemeris.py`：所有 `MultipleShooting(dynamics=...)` 添加 `n_workers=N_WORKERS, kernel_dir=SPICE_KERNEL_DIR`
- [x] 3. 修复 `homotopy_dro_to_ephemeris.py`：`BODIES` 改用 `BodyName`，添加 `N_WORKERS` 常量
- [x] 4. 同步修复 `compare_ephemeris_methods.py` 中相同问题
- [x] 5. 语法验证 + 模块导入验证

## 备注
- `convert_to_j2000` 函数签名：`tu_days: float = 4.34811305`，必须传天数而非秒数
- `MultipleShooting.__init__` 支持 `n_workers: int = 1, kernel_dir: Optional[str] = None`
- `BodyName.EARTH_MOON_SUN` = `['EARTH', 'MOON', 'SUN']`
- homotopy 脚本中 `run_homotopy_correction` 里有 3 处 `MultipleShooting()` 调用（主循环 + 子步）需要全部加并行参数
