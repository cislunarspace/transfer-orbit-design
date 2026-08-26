# ADR 0011：算法层直调（绕过 Facade 门面）

**状态**：已接受
**日期**：2026-08-04
**关联**：ADR 0006（e2m2e GUI 前端定位）

## 背景

e2m2e 的 Facade 门面（`e2m2e.api.Facade`）是 MCP/CLI 的统一入口。但 Facade 的返回值是 Pydantic 模型（`DesignOrbitResponse` 等），这些模型**剥离了轨道数据**：只返回标量汇总（轨道类型、Jacobi 常数、收敛标志），不返回 `Orbit` 对象或 `EphemerisTable`。

GUI 的可视化需要完整的轨道状态矩阵（`cr3bp_orbit.states` 形状 (n, 6)）和星历表（`ephemeris.position_km`）。这些数据被 Facade 门面丢弃了。

## 决策

GUI **直接调用 e2m2e 算法层**（`e2m2e.algorithm.design.design_orbit` 等），不经过 Facade 门面。

```python
# ✗ Facade 路径（丢失轨道数据）
response = facade.design_orbit(orbit_type="DRO", amplitude=40000)
# response 只有: orbit_type, cr3bp_jacobi, initial_state, correction_converged

# ✓ 算法层路径（完整数据）
result = design_orbit("DRO", amplitude=40000, kernel_dir="...")
# result 有: cr3bp_orbit (Orbit), ephemeris (EphemerisTable), correction, ...
```

## 理由

1. **可视化需要完整数据**：OrbitVisualizer 需要 `Orbit.states`，不是 `DesignOrbitResponse.initial_state`。
2. **Facade 是为 MCP/CLI 设计的**：MCP 传输层不需要 numpy 数组（JSON 序列化太重）。GUI 作为进程内集成者，可以直接使用 numpy 数据。
3. **性能**：省去 Facade 层的 Pydantic 序列化/反序列化开销。
4. **e2m2e 架构对齐**：e2m2e ADR 0011 明确算法层保留细粒度 API（专家用），GUI 就是这个专家用户。

## 后果

### 正面

- 可视化数据完整
- 无信息损失
- 调用链更短

### 负面

- 不经过 Pydantic 参数校验（需要在 GUI 侧自行校验，或在 FacadeBridge 中做轻量校验）
- 耦合 e2m2e 算法层的函数签名（签名变更会影响 tod）
- Facade 门面更新后不需要同步（双刃剑：灵活但可能 drift）

### 缓解措施

- FacadeBridge 薄封装：集中处理异常翻译和结果 DTO 转换
- e2m2e 算法层签名相对稳定（已被其自身测试套件覆盖）
- 如果 Facade 未来补全返回完整数据，可切换回 Facade 路径

## 修订（2026-08-17，e2m2e 5.7.1）

轨道族生成改走 `Facade.orbit_family_generation`：5.7.1 起 Facade 响应
（`FamilyGenerationResponse`）携带完整 `Orbit` 成员与状态三元组，软失败
保留部分族，七族统一入口。本 ADR 的前提（Facade 剥离轨道数据）对族生成
已不再成立；`design_orbit` / `control_orbit` 仍直调算法层（对应响应仍只
返回标量汇总）。

## 修订（Tauri 架构起，v4.0.0）

界面链路整体迁移到 e2m2e `serve-stdio` sidecar——算法只经 Facade 统一
入口进入界面（协议见 e2m2e ADR 0035）。本 ADR 的直调决策在界面上已无
使用者；直调式薄封装保留在 `src/engine/facade_bridge.py`，供脚本与测试。
“GUI 不再绕过门面直调算法层”见 `docs/architecture/architecture.md`。