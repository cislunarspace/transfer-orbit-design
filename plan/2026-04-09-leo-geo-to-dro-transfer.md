# LEO/GEO → DRO 转移轨道搜索与优化

## 目标
使用网格搜索 + NLP 优化方法，生成从近地轨道（LEO/GEO）到月球远距逆行轨道（DRO）的转移轨道，作为崔等(2025)方法的反方向扩展。

## 预研结果（已完成 ✓）
- **`TransferSearch` 可直接用于 GEO→DRO**（交换 departure/arrival 即可）
- GEO 近似圆轨道足够用于搜索阶段
- **有效 alpha 范围**：1.0 ~ 1.5（最佳约 1.37 ~ 1.42）
- 小规模测试找到 **28 个可行解**，最近 85 km

## 架构决策
- **搜索阶段**：复用 e2m2e 的 `TransferSearch`
- **优化阶段**：内联实现（与 `optimize_dro_geo.py` 模式一致）
- **不修改 e2m2e**：所有新代码在 scripts 中

## 新增文件清单
```
scripts/utils/leo.py                                    # LEO 常量和工具函数
scripts/transfer/grid_search_geo_to_dro.py              # GEO→DRO 网格搜索
scripts/transfer/optimize_geo_to_dro.py                 # GEO→DRO NLP 优化
scripts/transfer/grid_search_leo_to_dro.py              # LEO→DRO 网格搜索
scripts/transfer/optimize_leo_to_dro.py                 # LEO→DRO NLP 优化（包装脚本）
scripts/transfer/plot_search_results_geo_to_dro.py      # 搜索结果可视化（含交互式）
scripts/transfer/plot_optimize_result_geo_to_dro.py     # 优化结果可视化
scripts/transfer/validate_geo_to_dro.py                 # 技术预研验证脚本
```

## 任务列表

### 阶段 0：预研 ✓
- [x] 0.1 验证 `TransferSearch` 对 GEO 出发的适用性
- [x] 0.2 确定 GEO 在 CR3BP 坐标系中的参数

### 阶段 1：基础工具 ✓
- [x] 1.1 GEO 轨道生成函数（内联在搜索脚本中）
- [x] 1.2 LEO 工具模块 `scripts/utils/leo.py`

### 阶段 2：网格搜索 ✓
- [x] 2.1 GEO → DRO 网格搜索 `grid_search_geo_to_dro.py`
- [x] 2.2 LEO → DRO 网格搜索 `grid_search_leo_to_dro.py`

### 阶段 3：NLP 优化 ✓
- [x] 3.1 GEO → DRO 优化 `optimize_geo_to_dro.py`
- [x] 3.2 LEO → DRO 优化 `optimize_leo_to_dro.py`

### 阶段 4：可视化 ✓
- [x] 4.1 搜索结果可视化 `plot_search_results_geo_to_dro.py`（含交互式）
- [x] 4.2 优化结果可视化 `plot_optimize_result_geo_to_dro.py`

### 阶段 5：验证与文档
- [ ] 5.1 运行完整搜索验证结果
- [ ] 5.2 运行优化验证结果
- [ ] 5.3 添加测试用例
- [ ] 5.4 更新项目文档（CLAUDE.md, AGENTS.md）

## 使用流程
```bash
# 1. GEO→DRO 搜索
python scripts/transfer/grid_search_geo_to_dro.py

# 2. 更新搜索结果路径后运行优化
python scripts/transfer/optimize_geo_to_dro.py

# 3. 可视化
python scripts/transfer/plot_search_results_geo_to_dro.py --interactive
python scripts/transfer/plot_optimize_result_geo_to_dro.py --orbit

# LEO→DRO 流程相同，使用对应的 leo 脚本
python scripts/transfer/grid_search_leo_to_dro.py
python scripts/transfer/optimize_leo_to_dro.py
```
