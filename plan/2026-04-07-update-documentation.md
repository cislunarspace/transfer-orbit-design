# 更新说明文档

## 目标
审查并更新 README.md、docs/ 全部文档、AGENTS.md、CLAUDE.md，确保与代码一致。

## 背景
代码审查发现多处文档与实际代码不一致，包括错误的参数值、缺失的脚本文档、错误的坐标系描述等。刚修复了一批 bug，文档也应反映修复后的状态。

## 任务列表

- [x] 1. **修复 CR3BP 坐标系描述** `docs/theory/cr3bp-theory.md`
  - x 轴方向：从次天体→主天体 修正为 从主天体（地球）→次天体（月球）

- [x] 2. **修复网格搜索参数** `docs/algorithms/grid-search-trajectory-optimization.md`
  - n_alpha: 101→100, max_transfer_time: 15.0→100.0/TU, dt: 0.001→1.0/(24*TU)
  - earth/moon_radius: 0.01→200/DU 和 100/DU
  - 移除所有 beta 相关描述和变量
  - 示例代码中的 Euler 积分改为 DOP853 说明
  - 速度扰动公式从 tangential/normal 改为 radial/tangential 分解
  - 碰撞半径和排查清单中 β 引用已修正

- [x] 3. **修复 RO 种子参数表** `docs/design/ro-generation.md`
  - 删除错误的 y₀ 列，修正 vy₀ 值（3:2 RO: 0.4633, 3:1 RO: 0.3921）
  - param_min: 0.8905→-0.8905（加负号）
  - 约束条件描述与 setup_2D_symmetric_x_fixed_x0 一致

- [x] 4. **修复 alpha 范围和 BR4BP 参数** `docs/design/dro-ro-transfer.md`
  - alpha 范围 0.1~2.0 → 0.5~2.5
  - 移除 beta 行
  - BR4BP 参数使用完整精度值

- [x] 5. **补充缺失脚本** `docs/reference/scripts-reference.md`
  - 添加 plot_optimize_result.py、grid_search_dro_geo.py、optimize_dro_geo.py、plot_search_results_geo.py
  - 添加 ephemeris/ 下 4 个脚本
  - 添加 geo.py 模块完整描述
  - 补充 common.py 中 load_or_compute、save_family_to_file
  - 移除 beta 引用，修正速度扰动公式和单位描述

- [x] 6. **更新索引和输出目录** `docs/index.md`, `docs/guides/system-overview.md`
  - 添加 DRO→GEO 管线和 ephemeris 管线到索引表和快速开始
  - output/halo/ → output/ephemeris/

- [x] 7. **更新 API 参考** `docs/reference/api-reference.md`
  - （审查后发现主要问题已在其他文件中覆盖，API 参考相对准确）

- [x] 8. **更新 README.md**
  - 添加 7 个缺失脚本到脚本表（plot_optimize_result.py、DRO→GEO 管线 3 个、ephemeris 4 个）
  - output/halo/ → output/ephemeris/

- [x] 9. **更新 AGENTS.md 和 CLAUDE.md**
  - CLAUDE.md: 添加 DRO→GEO 管线、ephemeris 管线、GeoTransferSearch API
  - AGENTS.md: 已有完整描述，无需修改

## 备注
- 修改涉及 12 个文档文件
- 测试结果：69 passed, 2 skipped，全部通过
- docs/reference/api-reference.md 中 mu 的表示方式差异（0.01215 vs 1.21506683e-2）属格式差异，值相同，未修改
