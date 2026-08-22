# transfer-orbit-design 架构设计

> 本文描述 transfer-orbit-design（以下简称 tod）的**最终形态**架构。逐项架构决策见 `docs/adr/`。

## 总体定位

tod 是 **e2m2e 的 GUI 前端**。它不实现任何轨道力学算法，只做三件事：

1. **调用**——通过 e2m2e Facade API 发起计算任务（轨道设计、轨道族生成、轨道保持、稳定性分析）。
2. **管理**——追踪用户工作会话中的全部计算产物（轨道、轨道族、转移结果），提供结构化的数据导航和管线串联。
3. **呈现**——将计算结果以内嵌可视化的方式展示在主窗口中，支持 3D/2D 轨道图、多轨道叠加、地月系统标注。

用户不需要知道 e2m2e 的内部结构，也不需要手动管理文件路径。tod 把 e2m2e 的能力封装为"选工件 → 选操作 → 看结果"的三步交互。

## 总体分层

自 ADR-0014 起，GUI 为 Tauri 架构（Rust 壳 + React 前端），e2m2e 经
sidecar 子进程驱动（协议 = e2m2e ADR 0035：信封 JSON 行 + 二进制帧）。
原 PyQt 四层中的表现层/入口层已被替换，数据层与执行层的纯 Python 部分
保留为领域资产。

```
React 前端（frontend/） ←Tauri IPC→ Rust 壳（src-tauri/）
                                        ↕ stdio 协议
                                   e2m2e serve-stdio（uv 拉起）
```

| 层 | 位置 | 职责 |
|:---|:---|:---|
| 前端 | `frontend/src/` | React 组件：项目树、参数面板（schema 自动表单）、Three.js 画布、i18n、图表设置 |
| Rust 壳 | `src-tauri/src/` | sidecar 进程管理（拉起/重试/进度事件）、Tauri command、项目状态（内存 Artifact 容器） |
| sidecar 协议 | e2m2e 侧 | `serve-stdio`：信封 JSON 行 + f32/f64 二进制帧（大数组），见 e2m2e ADR 0035 |
| 领域层（Python） | `src/engine/`、`src/commons/`、`src/model/` | facade_bridge / catalog_service / 单位换算 / 内核管理——e2m2e 语义的 Python 侧资产，工具脚本与测试继续使用 |

**关键机制**：

- **schema 驱动表单**：工具入参 schema 构建期导出（`tools/export_tool_schemas.py` → `frontend/src/toolSchemas/`），参数面板自动生成；升级 e2m2e 后重跑导出。
- **帧即渲染**：sidecar f32 帧直达前端 `BufferAttribute`，无中间格式；族成员初态 + period 由前端 CR3BP 传播器重采样整条轨迹（方程对齐 e2m2e，有回归测试）。
- **视图保持**：布局不变的重绘不重置相机；首次数据到达做一次视图适配（CONTEXT.md 领域语义）。

## 顶层结构（最终形态）

```
transfer-orbit-design/
├── frontend/              # React 前端（Vite + TS + Three.js）
│   └── src/               # 组件、schema 驱动表单、i18n、画布、录制导出
├── src-tauri/             # Rust 壳（Tauri 2）
│   ├── src/sidecar/       # 帧解析（frames）+ 子进程管理（process）
│   ├── src/cmd.rs         # Tauri command（族生成/目录查询/项目状态）
│   └── tests/             # 协议夹具测试 + 真实子进程集成测试
├── src/                   # Python 领域层（纯 Python，无 Qt）
│   ├── model/             # Project/Artifact/discovery（数据类）
│   ├── engine/            # facade_bridge / catalog_service / persistence / viz_adapter
│   ├── commons/           # 跨层常量与共享工具
│   │   ├── constants.py   # DU/TU/物理常量
│   │   ├── units.py       # 单位换算（年/月/日/TU、km/DU）
│   │   ├── kernels.py     # 内核下载/可用性判断（CLI 与 GUI 共用）
│   │   ├── paths.py       # 内核/库目录探测与配置持久化
│   │   ├── orbits.py      # GEO/LEO 轨道几何
│   │   └── viz/           # 收编自 e2m2e tools/viz 的绘图组件（自维护）
│   └── __init__.py
├── docs/                  # 文档
│   ├── adr/               # 架构决策记录
│   ├── architecture/      # 架构说明
│   └── source/            # Sphinx 源（docs/README.md 说明维护流程）
├── tests/                 # 测试（app/commons/engine/model/view 分层）
├── scripts/               # 独立工具脚本（download_kernels.py）
├── catalog/               # 轨道库（e2m2e catalog，产物持久化源；设置可改指）
└── pyproject.toml
```

**删除的旧代码**（大爆炸替换）：

| 旧目录 | 原因 |
|---|---|
| `tod/gui/` | 被 `src/view/` + `src/app/` 替代 |
| `tod/generates/` | 被 e2m2e Facade API 直调替代 |
| `tod/transfers/` | 被 e2m2e Facade API 直调替代 |
| `tod/scripting/` | SCRIPT_ENTRY 机制废弃 |
| `tod/commons/e2m2e_compat.py` | 不再需要旧路径兼容 |
| `plot/`（顶层） | v3.2.1 起 e2m2e 删除 `tools/viz`，绘图组件收编为 `src/commons/viz/` 由本项目自维护 |

## 第1层 数据层 `src/model/`

### Artifact

一次计算的产出物。纯数据类，不依赖 Qt 或 e2m2e。

```python
@dataclass
class Artifact:
    artifact_id: str        # catalog 产物取 record_id；非 catalog 产物为 UUID 前 8 位
    artifact_type: str      # "orbit" | "family" | "transfer" | "ephemeris"
    label: str              # 用户可见名称
    orbit_type: str         # DRO/Halo/NRHO/...
    source_tool: str        # 产生此 Artifact 的 Facade 方法名（catalog_promote 为提升成员）
    record_id: str | None   # 轨道库记录 id（e2m2e catalog，issue #375）
    state_data: ndarray     # 状态矩阵 (n, 6)，用于可视化（catalog_get 懒加载填充）
    times: ndarray          # 时间向量 (n,)
    output_path: Path | None # 仅 transfer 遗留分区使用（指向 output/ JSON）
    extra: dict             # 元数据（分类、谱系指针、tags/note、星历四件套等）
    created_at: datetime    # 创建时间
```

### Project

管理一次工作会话的全部 Artifact。**Project 不做持久化**——清单由轨道库 catalog 承担（`catalog_query` 供数）。

```python
class Project:
    name: str
    artifacts: list[Artifact]

    def add(artifact) -> None
    def remove(artifact_id) -> bool
    def get_by_id(artifact_id) -> Artifact | None
    def get_by_type(type) -> list[Artifact]
    def get_by_orbit_type(orbit_type) -> list[Artifact]
    def find_upstream(artifact) -> Artifact | None  # 读 extra["source_record_id"] 谱系追溯
    def has_broken_lineage(artifact) -> bool        # 上游已删（断链降级标记）
```

### Discovery（遗留分区扫描）

转移轨道是 catalog 分类体系之外的产物（上游入库另行立项），过渡期沿用 `output/transfer/` 目录扫描；轨道 / 族 / 星历的文件名分类正则已随 catalog 接入删除（ADR 0008 修订 2026-08-19）。

```python
def discover_artifacts(output_dir: Path) -> list[Artifact]:
    """扫描 output/transfer/ 下的 JSON（corrected_transfer_* / optimization_*），
    构建 transfer Artifact 列表。"""
```

## 第2层 执行层 `src/engine/`

### FacadeBridge

e2m2e Facade API 的薄封装。处理配置注入（kernel_dir / catalog_dir 经 `Config`）、异常翻译、catalog 读写转发。

```python
class FacadeBridge:
    def __init__(self, kernel_dir=None, catalog_dir=None, facade=None): ...

    def design_orbit(self, **params) -> OrbitDesignResultData:
        """经 Facade 调用 design_orbit，返回可跨线程传递的结果 DTO；
        产物自动入轨道库（record_id 回执）。"""

    def generate_family(self, **params) -> FamilyResultData: ...
    def analyze_stability(self, **params) -> StabilityResultData: ...
    def control_orbit(self, ephemeris_data, source_mu, **params) -> ControlResultData:
        """input_record_id 直连库中记录（Facade 解析星历段并写谱系），
        无记录时回退内存星历重建 EphemerisTable。"""

    # catalog 薄封装：catalog_query / catalog_get / catalog_tag /
    # catalog_delete / catalog_promote / catalog_export
```

**关键设计**：

- **三个计算工具统一走 Facade 门面**（issue #375，完成 ADR 0011 缓解措施 3 的既定清理）：#312 起 Facade 响应携带完整几何字段（states/times/mu/ephemeris），#475（e2m2e 5.8.0）起产物自动入轨道库、`control_orbit` 支持 `input_record_id` 谱系输入。GUI 不再绕过门面直调算法层。
- **周期族成员只携带初态与周期**，桥接层按周期重采样供画布渲染（catalog 族记录懒加载复用同一辅助函数）。
- **e2m2e 5.6.5 起 `design_orbit` 首参为 `DesignOrbitRequest`**（散字段不再支持），Facade 校验请求；`duration` 由面板年单位换算为秒，Lissajous 固定注入 segmented 修正。
- **结果 DTO（Data Transfer Object）**：可跨线程边界传递的纯数据类，不持有 e2m2e 对象引用。包含 numpy 数组（状态矩阵、时间向量）、标量元数据与 `record_id`（入库回执）。
- **异常翻译**：e2m2e 异常 → 结构化错误码 + 用户友好消息（`src/engine/exceptions.py`）；Facade 接缝的 `e2m2e.api.OrbitError` 透传错误码。

### CatalogService

轨道库的 GUI 语义层（`catalog_service.py`）：摘要 → Artifact 映射（清单）、`catalog_get` 懒加载填充（design 双段 / family 成员堆叠与重采样 / control 星历减 μ）、标注 / 提升 / 导出 / 删除转发。GUI 测试用桩 bridge 或小型真实库，不重测上游。

### Workers

（原 QThread Worker 机制已随 PyQt UI 一并移除：计算任务经 Tauri command →
sidecar 子进程完成，线程管理由 Rust tokio 承担。）
## 前端与 Rust 壳

组件级说明见源码：`frontend/src/`（App 三栏布局、ParamsPanel schema 表单、
OrbitCanvas Three.js 画布、CatalogFilterBar、i18n、chartSettings）与
`src-tauri/src/`（sidecar 模块、cmd.rs、state.rs、project.rs）。

## 依赖方向规则

```
src/app/     →  src/view/ + src/engine/ + src/model/
src/view/    →  src/model/ + src/engine/（仅 workers 的信号类型）
src/engine/  →  src/model/（仅 Artifact/Project 类型）+ e2m2e
src/model/   →  numpy（纯数据）
src/commons/ → 无依赖（常量）；其中 `src/commons/viz/` 为收编的第三方绘图组件，仅依赖 e2m2e 数据类型（不承担本仓类型标准，见 `pyproject.toml` 的 pyright exclude）
```

**硬规则**：

1. `src/model/` 不 import `src/view/` 或 `src/engine/`。
2. `src/view/` 不直接 import e2m2e。所有 e2m2e 调用经 `src/engine/` 桥接。
3. `src/engine/` 不 import 任何 GUI 框架（Qt 依赖已随 PyQt UI 移除）。
4. `src/commons/` 不被 `src/model/`、`src/engine/`、`src/view/` 反向依赖（commons 是叶子）。

## 可视化架构

### 画布内部结构

```
FigureCanvasQTAgg
└── Figure (8x6, dpi=100)
    └── Axes (3d 或 2d，由 projection 切换)
        ├── 轨道线 (Line3D / Line2D)
        ├── 起点标记 (scatter)
        ├── 地球 (scatter + icon, show_bodies=True)
        ├── 月球 (scatter + icon, show_bodies=True)
        └── 拉格朗日点 L1-L5 (scatter + label, show_libration=True)
```

### 渲染流程

```
用户点击 Artifact
  → Project.get_by_id()
  → CanvasState 更新 visible_artifacts
  → canvas.render(CanvasState)
    → 根据 projection 创建 Axes (3d / 2d / quad)
    → 根据 frame 选择坐标系（synodic：无量纲；inertial：GCRS km）
    → 遍历 visible_artifacts，按 plot_content 绑定 state_data / 星历数组
    → 如果 show_bodies: 绘制地月位置（inertial 下月球沿 SPICE 轨迹移动）
    → 如果 show_libration: 绘制 L1-L5（仅 synodic）
    → fig.tight_layout() + canvas.draw()
```

### 颜色策略

- 单轨道：tab10 调色板首个颜色
- 多轨道叠加：tab10 调色板自动分配；颜色方案可在图表设置中切换
- 轨道族：m 条成员按 viridis colormap 渐变着色
- 叠加视图：初猜实线、星历虚线，TAB10 相邻色区分
- 起点：绿色圆点；终点：红色圆点
- 地球：蓝色大圆 + 图标；月球：灰色大圆 + 图标；L 点：黑色三角 + 标签

## 管线串联

用户操作一个 Artifact 后，项目树的右键菜单展示可用的下一步操作。

**因果链**（谱系持久化，重启不断）：

```
Artifact A (DRO orbit, 含星历段, record_id=R1)
  → 右键 → "轨道保持" → 调 control_orbit(input_record_id=R1)
    → 产物自动入库为 Artifact B (ephemeris)，source_record_id=R1
    → R1 被删后项目树显示 "受控星历 ⚠断链"，B 仍可用
  → 右键 → "稳定性分析" → 调 analyze_stability(states=A.state_data)
    → 显示结果弹窗 + 落盘 output/stability/
```

**数据流**：Artifact 的 `state_data` / 星历数组在内存中传递（numpy 数组引用），不经过文件 I/O。持久化是并行行为——计算产物经 Facade 自动入轨道库（重启后由 `catalog_query` + `catalog_get` 懒加载恢复）。

## 工具范围（当前）

GUI 的工具范围固定为四件：轨道设计、轨道保持、轨道族生成（Halo 北族）、
稳定性分析（右键）。e2m2e 的转移设计、低推力、流形分析等能力**不在 GUI
范围内**——需要脚本化工作流时直接使用
[e2m2e CLI](https://github.com/cislunarspace/e2m2e)。这与早期版本"灰显
占位等待 e2m2e 实现"的策略不同：不承诺 GUI 承载全部算法能力，避免维护
一批永远点不亮的按钮。

## 依赖

- **运行时**：numpy, scipy（Python 领域层）；Rust/Tauri 2 + Node/Vite（前端与壳，各自锁文件管理）
- **e2m2e**：PyPI 依赖（`e2m2e>=5.6.8`），运行时经 `src/engine/facade_bridge.py` 调用 algorithm 层
- **calcephpy**：经 e2m2e→r2s2 传递依赖（Windows 用预编译 wheel，见 `pyproject.toml` 的 `[tool.uv.sources]`）
- **可选**：PyInstaller（打包为 Windows 便携版）

## 测试策略

| 层级 | 测试类型 | 覆盖目标 |
|---|---|---|
| model/ | 单元测试 | Artifact CRUD、Project 查询、Discovery 扫描 |
| engine/ | 集成测试 | FacadeBridge → e2m2e（真实参数模型签名）、持久化落盘、异常翻译 |
| view/ | 控件测试 | 参数面板生成/收集、画布渲染、项目树交互、图表设置 |
| app/ | 集成测试 | 内核引导、主窗口工具调度、i18n 加载 |
| commons/ | 单元测试 | 单位换算、内核下载/可用性判断、路径探测 |

e2m2e 本身已通过其自身测试套件验证，tod 不重复测试 e2m2e 的计算正确性。tod 的测试关注 GUI 行为和数据流。
