# 开发指南

## 文档规范

本项目的文档面向中文研究用户和维护者，所有新增 README、Sphinx 页面、GUI 描述、CLI help 与 docstring 均使用中文。Python docstring 采用 Google style，以便 `sphinx.ext.napoleon` 自动解析。

### 模块级 docstring

每个 `src/` 生产模块都必须包含模块级 docstring，并放在文件第一条语句。建议结构：

```python
"""FacadeBridge -- e2m2e 算法层直调的薄封装。

直接调用 algorithm 层而非 Facade 门面，因为 Facade 返回的 DesignOrbitResponse
剥离了轨道数据（只返回标量汇总），而 GUI 需要完整的 Orbit 对象用于可视化。
详见 docs/adr/0011-algorithm-layer-direct-call.md。
"""
```

不同模块类型的重点如下：

| 类型 | 必写内容 |
|------|----------|
| 数据层（`src/model/`） | 数据类的字段含义、与持久化（catalog / output）的对应关系 |
| 执行层（`src/engine/`） | 调用的 e2m2e 算法、返回 DTO 的字段、异常翻译、落盘布局 |
| 前端（`frontend/src/`） | 组件职责、props 语义、与 IPC/画布的交互 |
| Rust 壳（`src-tauri/src/`） | 命令语义、sidecar 进程与协议边界、状态生命周期 |
| 工具脚本（`scripts/`） | 用途、参数、输出 |

### 函数与类 docstring

公共函数、公共类和 dataclass 使用单行摘要 + `Args` / `Returns` / `Raises` 的 Google-style 格式。不要在 `Args` 中重复 type hint，只写含义、单位和约束。

```python
def load_orbit(path: Path) -> dict:
    """读取轨道 JSON 文件并返回原始载荷。

    Args:
        path: 轨道 JSON 文件路径。

    Returns:
        解析后的 JSON 字典，包含 `states`、`times` 和 `period` 等键。

    Raises:
        FileNotFoundError: 输入文件不存在。
        ValueError: JSON 内容缺少轨道状态字段。
    """
```

`main()` 和 `parse_args()` 也需要 docstring：`parse_args()` 说明返回解析后的命名空间；`main()` 说明执行完整脚本流程且通常不返回值。私有 helper 可以使用较短 docstring，但仍应说明单位、边界或失败条件。

### CLI help 文本（工具脚本）

`scripts/` 下的独立工具脚本中，目前仅有 `download_kernels.py`，使用 `argparse`。help 文本必须回答三个问题：参数控制什么、默认值是什么、单位是什么。示例：

```python
parser.add_argument(
    "--position-tol",
    type=float,
    default=1e-3,
    help="多重打靶位置连续性容差，默认 1e-3 km。",
)
```

无量纲 CR3BP 参数应注明为无量纲；角度单位写 rad 或度；时间单位写 TU、天或秒。布尔开关说明开启后的行为。

### 国际化

界面 i18n 在前端 `frontend/src/i18n.ts`：中英两份字符串字典，`t(key)` 取用，
语言选择存 localStorage、重启保留。新增界面文本时同步向两个字典各加一条键值；
新增语种则追加一份字典。（PyQt 时代的 `tools/update_i18n.py` 与 `src/app/i18n/`
已随旧 UI 删除。）

### Sphinx 文档

Sphinx 源文件位于 `docs/source/`，叙事文档通过 MyST Markdown 接入。

```bash
uv run --extra docs python -m sphinx -b html docs/source docs/build/html
```

提交前应至少确认构建无 ERROR，并尽量清理 WARNING。若新增/删除叙事页面，请在 `docs/source/index.rst` 的对应 toctree 中增删条目，并同步更新英文 `.po`（见 `docs/README.md` 的 `sphinx-intl update` 流程）。

### 多语言 README

- `README.md` 为中文主文档；其他语言版本命名为 `README.<lang>.md`（当前仅有 `README.en.md`）。
- 修改任一语言版本时，应在同一提交中同步其余版本，保持章节结构一一对应。
- 代码块、命令、路径、模块名一律不翻译；标题翻译后需同步修正文内锚点链接。
- 各语言版本顶部均应放置语言切换链接。

## 日志与打印

本项目使用 Python `logging` 模块而非 `print()` 进行输出。

### 日志级别

| 级别 | 数值 | 说明 |
|------|------|------|
| `DEBUG` | 10 | 详细调试信息 |
| `INFO` | 20 | 一般信息 |
| `WARNING` | 30 | 警告（默认级别） |
| `ERROR` | 40 | 错误 |
| `CRITICAL` | 50 | 严重错误 |

默认日志级别为 `WARNING`，只有更高级别的日志会输出。

### 使用规范

脚本入口模块应配置 logging：

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)
```

使用 `logger.info()`、`logger.debug()` 等代替 `print()`。这使得：
- 可通过调整日志级别控制输出详细程度
- 支持日志处理器（如写入文件）
- 输出带有时间戳、模块名等上下文信息

### 调试模式

运行脚本时设置环境变量可临时调整日志级别：

```bash
# 显示 INFO 及以上
set PYTHONLOGLEVEL=INFO

# 显示所有日志（包括 DEBUG）
set PYTHONLOGLEVEL=DEBUG
```