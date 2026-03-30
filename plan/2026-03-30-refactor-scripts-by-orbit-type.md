# 重构 scripts 目录：按轨道类型组织

## 目标
将 scripts/generate/ 和 scripts/plot/ 按轨道类型重组为 scripts/dro/、scripts/halo/、scripts/ro/，删除 scripts/extract/，通用脚本移至 scripts/ 根目录。

## 文件映射

### scripts/dro/
- [ ] generate_31_dro_orbit.py ← generate/generate_31_dro_orbit.py
- [ ] generate_dro_family.py ← generate/generate_dro_family.py
- [ ] plot_dro_family.py ← plot/plot_dro_family.py
- [ ] extract_31_dro_orbit.py ← extract/extract_31_dro_orbit.py
- [ ] extract_32_dro_orbit.py ← extract/extract_32_dro_orbit.py

### scripts/halo/
- [ ] generate_halo_orbit.py ← generate/generate_halo_orbit.py
- [ ] generate_halo_family.py ← generate/generate_halo_family.py
- [ ] plot_halo_orbit.py ← plot/plot_halo_orbit.py
- [ ] plot_halo_family.py ← plot/plot_halo_family.py

### scripts/ro/
- [ ] generate_31_ro_orbit.py ← generate/generate_31_ro_orbit.py
- [ ] generate_31_ro_family.py ← generate/generate_31_ro_family.py
- [ ] generate_32_ro_family.py ← generate/generate_32_ro_family.py
- [ ] generate_aro_family.py ← generate/generate_aro_family.py
- [ ] generate_rro_family.py ← generate/generate_rro_family.py
- [ ] plot_31_ro_family.py ← plot/plot_31_ro_family.py
- [ ] plot_32_ro_family.py ← plot/plot_32_ro_family.py
- [ ] plot_aro_family.py ← plot/plot_aro_family.py
- [ ] plot_rro_family.py ← plot/plot_rro_family.py
- [ ] extract_31_ro_orbit.py ← extract/extract_31_ro_orbit.py
- [ ] extract_32_ro_orbit.py ← extract/extract_32_ro_orbit.py

### scripts/ 根目录（通用）
- [ ] plot_single_orbit.py ← plot/plot_single_orbit.py
- [ ] plot_interactive_orbit_inspector.py ← plot/plot_interactive_orbit_inspector.py

## 任务列表
- [x] 1. 创建目录 scripts/dro/, scripts/halo/, scripts/ro/
- [x] 2. git mv 移动所有文件到新位置
- [x] 3. 更新 plot_dro_family.py 的 import（从 scripts.utils.params 改为 scripts.utils.common）
- [x] 4. 更新 plot_single_orbit.py 的 import 和 project_root 深度
- [x] 5. 删除空的 generate/, plot/, extract/ 目录及其 README.md
- [x] 6. 更新 tests/scripts/ 中的路径引用
- [x] 7. 运行测试验证 (60 passed, 2 skipped)

## 备注
- 所有脚本的 `from scripts.utils.common import ...` 路径不变（utils/ 保持原位）
- generate_dro_family.py 和 generate_halo_*.py 中有 `sys.path.insert` hack，移动后层级不变可删除
- extract 脚本移入对应轨道目录，不再单独成目录
- transfer/ 目录不变
