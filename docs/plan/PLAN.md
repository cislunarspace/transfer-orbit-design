# 任务计划：system.py 和 grid_search.py 重构

## 目标

1. 解决 `system.py` 中 TODO 关于参数管理的需求
2. 修复 `grid_search.py` 中的代码问题
3. 重构并统一参数管理
4. 编写/修改测试用例

---

## 发现的问题

### system.py
- `EARTH_MOON_DISTANCE_KM = 384400.0` 值不准确，且参数分散在不同地方

### grid_search.py
1. **第36-37行**：重复创建 `system` 对象，第二次覆盖第一次
2. **第36行**：`MU` 值 (`1.21506683e-2`) 与第37行硬编码 (`0.01215`) 不一致
3. **第76行**：变量名 `dynamics` 实际应为 `dynamic`（第42行定义）
4. **第46行**：`max_step` 计算有误

---

## 阶段一：统一参数管理

- [ ] 创建 `e2m2e/core/parameters.py` 定义地月系统精确参数
- [ ] 更新 `CR3BP_System` 使用新的参数类
- [ ] 删除 `system.py` 中的 TODO 注释

## 阶段二：修复 grid_search.py

- [ ] 修复重复创建 system 对象的问题
- [ ] 统一使用 e2m2e.core 中的参数
- [ ] 修复 `dynamics` → `dynamic` 变量名错误
- [ ] 修复 `max_step` 计算

## 阶段三：测试验证

- [ ] 编写 `tests/core/test_system.py` 测试 CR3BP_System
- [ ] 编写 `tests/core/test_parameters.py` 测试参数类
- [ ] 验证 grid_search.py 可正常运行

---

## 参考信息

### 相关文件
- `/home/desktop/codes/transfer-orbit-design/e2m2e/core/system.py`
- `/home/desktop/codes/transfer-orbit-design/scripts/transfer/grid_search.py`
- `/home/desktop/codes/transfer-orbit-design/scripts/utils/common.py`

### 当前参数值 (scripts/utils/common.py)
```python
MU = 1.21506683e-2      # 质量比
DU = 3.84405000e5      # 距离单位 km
TU = 4.34811305         # 时间单位 days
VU = 1023.23281         # 速度单位 m/s
```

### 现有测试文件
- `tests/scripts/test_plot_scripts_helpers.py`
- `tests/scripts/test_generate_family_helpers.py`
- `tests/scripts/test_params.py`
- `tests/scripts/test_common_utils.py`
- `tests/scripts/test_data_loading.py`
