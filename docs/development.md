# 开发指南

## 文档规范

本项目的文档面向中文研究用户和维护者，所有新增 README、Sphinx 页面、GUI 描述、CLI help 与 docstring 均使用中文。Python docstring 采用 Google style，以便 `sphinx.ext.napoleon` 自动解析。

### 模块级 docstring

每个 `tod/` 生产模块都必须包含模块级 docstring，并放在文件第一条语句。建议结构：

```python
"""生成 DRO 轨道族。

本模块在地月 CR3BP 中从已知 DRO 种子轨道出发，通过微分修正和自然延拓生成轨道族。
输入为命令行参数中的初始状态、周期猜测和延拓范围；输出为 `output/dro/` 下的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.dro.generate_dro_family --step-size 0.005
"""
```

不同脚本类型的重点如下：

| 类型 | 必写内容 |
|------|----------|
| 轨道生成 | 物理模型、种子轨道/延拓方法、输出目录、典型命令 |
| 转移搜索 | 输入轨道文件、搜索网格含义、筛选准则、输出 JSON |
| 转移优化 | 输入搜索结果、优化变量/目标、主要约束、失败处理 |
| 星历转换 | CR3BP 输入、参考历元、SPICE kernel 需求、修正方法 |
| 绘图 | 输入结果文件、可选图层、显示/保存行为 |
| GUI wrapper | 引用底层脚本，说明 GUI 中展示的参数与输出 |

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

### CLI help 文本

`argparse` help 文本必须回答三个问题：参数控制什么、默认值是什么、单位是什么。示例：

```python
parser.add_argument(
    "--position-tol",
    type=float,
    default=1e-3,
    help="多重打靶位置连续性容差，默认 1e-3 km。",
)
```

无量纲 CR3BP 参数应明确写“无量纲”；角度写“rad”或“度”；时间写“TU”“天”或“秒”。布尔开关说明开启后的行为。

### GUI 描述文本

`ScriptEntry.description` 使用 2–3 句中文描述，按“目的 + 输入 + 输出”组织。`CliParam.help` 与 CLI help 保持同义，并写明默认值和单位。星历转换类脚本必须提示 `SPICE_KERNEL_DIR` 或 `--spice-kernel-dir`。

```python
ScriptEntry(
    description=(
        "在地月 CR3BP 中生成 DRO 轨道族，用于后续转移搜索或绘图。"
        "脚本读取 GUI 中填写的种子状态、周期猜测和延拓范围。"
        "结果保存到 output/dro/，包括带时间戳的轨道族 JSON 和 latest 副本。"
    ),
)
```

### 国际化工具

`tools/update_i18n.py` 用于维护 GUI 的翻译文件：

```bash
python tools/update_i18n.py          # 提取 + 编译
python tools/update_i18n.py --extract # 仅提取待翻译字符串
python tools/update_i18n.py --compile # 仅编译 .ts → .qm
```

脚本执行三个步骤：
1. 用 `pylupdate6` 从 `tod/gui/` 提取待翻译字符串到 `tod/gui/i18n/gui.en.ts`
2. 用 `lrelease6` 编译所有 `.ts` 文件为 `.qm` 二进制格式
3. 校验 `tod/gui/i18n/scripts.*.json` 的 JSON 格式

依赖：`pylupdate6` 和 `lrelease6`（来自 PyQt6 或 PySide6 工具包）。新增 GUI 文本后应运行此脚本更新翻译文件。

### Sphinx 文档

Sphinx 源文件位于 `docs/source/`。API 页面使用 `automodule`，叙事文档通过 MyST Markdown 接入。

```bash
uv run --extra docs python -m sphinx -b html docs/source docs/build/html
```

提交前应至少确认构建无 ERROR，并尽量清理 WARNING。若新增公开模块，请在对应 `docs/source/tod/` toctree 中加入页面。

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
