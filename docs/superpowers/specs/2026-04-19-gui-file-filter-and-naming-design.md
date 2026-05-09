# GUI 文件过滤器与轨道命名规范设计

## 背景

GUI 界面中，Plot 类脚本的文件选择器无法区分单轨道文件和轨道族文件。例如 `plot_dro_family` 的下拉菜单中显示了所有 `output/dro/` 下的文件（包括单轨道 `dro_31_*.json`），但实际上只应该显示族文件 `*_family_*.json`。

与此同时，轨道文件的命名本身也存在不一致：单轨道与轨道族的命名格式不统一，ARO/RRO 族文件缺少参数范围信息。

---

## 需求一：GUI 文件下拉框按文件名模式过滤

### 方案 A（采用）

在 `CliParam` 和 `EnvParam` 中增加 `name_pattern` 字段（glob 模式），下拉框只显示匹配的文件。现有 `file_category` 逻辑保持不变。

### 改动范围

#### 1. 

`filter_files` 增加 `name_pattern: str | None` 参数：

```python
from fnmatch import fnmatch

def filter_files(
    files: list[FileInfo],
    category: str | None = None,
    file_type: str | None = None,
    name_pattern: str | None = None,
) -> list[FileInfo]:
    result = files
    if category:
        result = [f for f in result if f.category == category]
    if file_type:
        result = [f for f in result if f.file_type == file_type]
    if name_pattern:
        result = [f for f in result if fnmatch(f.name, name_pattern)]
    return result
```

#### 2. 

**`CliParam` 和 `EnvParam` 新增字段：**

```python
@dataclass(frozen=True)
class CliParam:
    # ... 现有字段 ...
    name_pattern: str | None = None  # glob 模式，如 "*_family_*.json"

@dataclass(frozen=True)
class EnvParam:
    # ... 现有字段 ...
    name_pattern: str | None = None
```

**需要设置 `name_pattern` 的脚本条目：**

| 脚本 | 参数 | name_pattern |
|------|------|-------------|
| `plot_dro_family` | `--json-file` | `"*_family_*.json"` |
| `plot_31_ro_family` | `--json-file` | `"*_family_*.json"` |
| `plot_32_ro_family` | `--json-file` | `"*_family_*.json"` |
| `plot_aro_family` | `--json-file` | `"*_family_*.json"` |
| `plot_rro_family` | `--json-file` | `"*_family_*.json"` |
| `plot_halo_family` | env `json_file` | `"*_family_*.json"` |
| `plot_halo_orbit` | `--json-file` | `"*_family_*.json"` |

#### 3. 

三处调用 `filter_files` 的位置都需要传入 `name_pattern`：

- `_make_cli_widget`（文件下拉框初始化，line ~1030）
- `_on_path_mode_changed`（路径模式切换时重填，line ~969）
- `_rebuild_params_panel`（EnvParam 文件填充，line ~1269）

---

## 需求二：统一轨道文件命名规范

### 命名规则

```
# 单轨道
{type}_{ratio}_{ts}.json

# 轨道族
{type}_{ratio}_family_{pmin}-{pmax}-{step}_{ts}.json
```

其中 `ts = int(time.time())`。

### 改动文件

| 文件 | 改动 |
|------|------|
|  | 输出文件名改为 `dro_31_{ts}.json`（当前已是） |
|  | 输出文件名改为 `dro_31_family_{pmin}-{pmax}-{step}_{ts}.json`（当前缺少 `_31`） |
|  | 输出文件名改为 `ro_31_{ts}.json`（当前已是） |
|  | 输出文件名改为 `ro_31_family_{pmin}-{pmax}-{step}_{ts}.json`（当前已是） |
|  | 输出文件名改为 `ro_32_family_{pmin}-{pmax}-{step}_{ts}.json`（当前缺少 `_32` 前缀中的 32） |
|  | 输出文件名改为 `aro_32_family_{pmin}-{pmax}-{step}_{ts}.json`，补充参数范围 |
|  | 输出文件名改为 `rro_32_family_{pmin}-{pmax}-{step}_{ts}.json`，补充参数范围 |
|  | 输出文件名改为 `halo_{L}_{N|S}_{amp}_{ts}.json`（当前已类似） |
|  | 输出文件名改为 `halo_{L}_{N|S}_family_{amp}_{ts}.json`，补充参数范围 |

### Halo 族命名补充说明

Halo 族的参数范围不好用 `param_min-param_max-step` 表示（振幅是连续值），统一为：

```
halo_{L}_{N|S}_family_{amp}_{ts}.json
```

其中 `amp` 是起始振幅值。

---

## 实施顺序

1. 先改 `file_discovery.py`（加 `name_pattern` 参数）
2. 再改 `script_registry.py`（加字段 + 填入 `name_pattern` 值）
3. 再改 `main_window.py`（三处调用处传入 `name_pattern`）
4. 最后改各个生成脚本的输出文件名

这样可以逐阶段验证，不易出错。
