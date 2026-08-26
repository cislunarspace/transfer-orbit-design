# 0015. UI 组件库选型与参数覆写层架构

- 日期: 2026-08-24
- 状态: 已接受（组件库现为 Ant Design 6，选型理由不变）

## 上下文

GUI 自 PyQt 大爆炸重构迁移到 Tauri 2（ADR-0014）后，原有的丰富交互（单位切换、tooltip 范围提示、分支默认值、右键菜单、模态弹窗、详情面板）以及界面视觉规范发生缺失。

在补齐 PyQt 24 项能力以及 e2m2e 14 个公开工具的表单需求时，需要做出两项关键技术决策：
1. **界面组件库选型**：原生 HTML 控件缺乏高密度科学计算所需的步长控制、Tooltip、树形右键、模态弹窗及暗黑主题体系。
2. **参数范围/提示/单位权威源**：e2m2e Pydantic 模型提供基础类型与数学约束，但缺失 GUI 特定的 17 个字段物理单位换算、富文本 tooltip 提示，以及部分 GUI 认知默认值（如 DRO 60000 km 相对上游 10000 km 标定默认）。

## 决策

1. **引入 Ant Design 5.x (`antd`) 作为统一 UI 组件库**：
   - 使用 Ant Design 的 `Form`、`InputNumber`（支持前缀/后缀单位与 step/min/max）、`Select`、`Tree`、`Modal`、`Dropdown`（右键菜单）、`Tooltip` 等组件。
   - 使用 antd 自带的 `ConfigProvider` 与 `theme.darkAlgorithm` / `theme.defaultAlgorithm` 实现全局亮色/暗色主题切换，配合字号配置对齐 PyQt 版 8–16pt 规范。

2. **建立前端参数覆写层 (`frontend/src/paramOverlay/`)**：
   - **基础约束**以 e2m2e 导出的 JSON Schema 为基底（单一事实来源）。
   - **覆写层**定义静态映射字典：
     - `UNIT_DEFINITIONS`: 17 个字段的单位定义（km/m/DU、周期份额/度/弧度、年/月/日/时/秒/TU 等）及其换算系数、小数精度与步长。
     - `BRANCH_DEFAULTS`: 15 种轨道类型与各族的 GUI 认知默认值表。
     - `FIELD_TOOLTIPS`: 字段多行描述、严格边界提示（> / < / ~）与物理含义解释。
     - `ENUM_LABELS`: 整数枚举（如 `collinear_point`, `north_south`, `control_mode` 等）的人读中文/英文显示映射。
   - 表单生成引擎读取 Schema + 覆写层，自动合成带有单位下拉、范围占位提示、完整 Tooltip 与必填星号的控件，表单提交时统一由覆写层换算回 e2m2e 标准物理单位。

## 结果

### 正向影响
- 科学计算高密度表单与树控件无需从头手搓，开发效率高、交互规范。
- 保证上游 e2m2e 模型纯粹性的同时，完整恢复 PyQt 版所有精细的参数提示、单位换算与分支交互。
- 主题切换与字号调节开箱即得。

### 负向影响与代价
- 前端 bundle 体积增加（约增加 antd 及其依赖），但作为桌面端应用（Tauri）对几十 KB 体积不敏感。
