# ADR 0010：内嵌可视化替代弹窗

**状态**：已接受；其 PyQt/matplotlib 实现路径已被 ADR 0014（UI 迁移到 Tauri，画布改用 Three.js）取代，仅“内嵌于主窗口、不弹外部窗”的原则仍然有效
**日期**：2026-08-04
**关联**：`docs/architecture/architecture.md`（可视化架构）

## 背景

旧 GUI 的可视化完全依赖外部 matplotlib 窗口（`plt.show()` 弹出独立 Tk 窗口）。用户需要在 PyQt GUI 和 matplotlib 弹窗之间来回切换，体验割裂。

新架构需要将可视化集成到主窗口内。

## 决策

使用 `matplotlib.backends.backend_qtagg.FigureCanvasQTAgg` 将 matplotlib Figure 嵌入 PyQt6 主窗口。配合 `NavigationToolbar2QT` 提供交互工具栏。

标准可视化能力（MVP）：

1. **3D 轨道图**：CR3BP 旋转坐标系
2. **2D 投影切换**：XY / XZ / YZ 三视图
3. **多轨道叠加**：选中多个 Artifact 时叠加渲染
4. **地月系统标注**：地球、月球位置 + 五个拉格朗日点
5. **轨道族热力图**：Jacobi 常数着色
6. **导航工具栏**：缩放/平移/旋转/保存图片

## 理由

1. **消除上下文切换**：用户在同一窗口内完成操作 → 查看全流程。
2. **FigureCanvasQTAgg 成熟**：matplotlib 官方支持的 Qt 嵌入方案，API 稳定。
3. **NavigationToolbar2QT 复用**：不需要自己实现缩放/旋转/保存逻辑。
4. **e2m2e OrbitVisualizer 兼容**：`OrbitVisualizer.plot_3d_orbit()` 接受可选 `ax` 参数，可以传入嵌入式 Axes。

## 后果

### 正面

- 用户体验从两个窗口变为一个窗口
- 可以利用 Qt 布局系统控制画布大小和位置
- 支持未来扩展（如拖拽 Artifact 到画布区域直接渲染）

### 负面

- matplotlib 的 3D 渲染性能有限（大量点时旋转卡顿）
- FigureCanvasQTAgg 的 DPI 处理在高分屏上需要额外适配
- CJK 字体需要显式配置（复用 `tod/plot/_font_config.py`）

### 后续

- 如果 matplotlib 3D 性能不满足需求，可考虑 PyVista/VTK 替代
- 可增加画布分屏（2x2 多视图）