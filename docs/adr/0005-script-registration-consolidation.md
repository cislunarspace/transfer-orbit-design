# ADR-0005: 脚本注册前后端合并

## 状态

已接受

## 上下文

每个 GUI 可运行脚本在 `tod/gui/scripts/` 下有镜像文件，只声明 `SCRIPT_ENTRY`（含 `CliParam` 列表）。实现脚本的 argparse 参数和镜像文件的 `CliParam` 描述同一批参数（flag、type、default、help），手动保持同步。

这是典型的 shotgun surgery：新增一个 CLI 参数需要编辑两个文件。`test_cli_default_consistency.py` 只覆盖 dropdown 参数的默认值漂移，非 dropdown 参数（如 `--x0`、`--vy0`）无自动检测。

镜像目录存在的原因是 ADR-0002 的约束：GUI 扫描阶段不能触发重型依赖（scipy、e2m2e）。镜像文件只导入轻量的 `script_registry.py`，避免在扫描时 import 实现脚本。

## 决策

将 `SCRIPT_ENTRY` 搬到实现脚本底部，删除镜像目录 `tod/gui/scripts/` 下的全部 47 个文件。扫描器改为扫描实现目录（`tod/generates/`、`tod/plot/`、`tod/transfers/`）。

关键设计选择：

1. **启动时间不重要**：扫描时 import 实现脚本会触发重型依赖加载，但计算本身才是耗时的。可以做加载界面告知用户进度，不需要为启动速度维护重复文件。

2. **SCRIPT_ENTRY 放在实现脚本底部**：`if __name__ == "__main__"` 块之后。参数定义（argparse）和 GUI 元数据（CliParam）在同一文件，新增参数只改一处。

3. **扫描器跳过加载失败的文件**：实现脚本可能因依赖缺失（如 e2m2e 版本不匹配）无法加载。扫描器捕获异常并静默跳过，不影响其余脚本的注册。

4. **`importlib` 加载需注册 `sys.modules`**：实现脚本中的 `@dataclass` 装饰器需要模块在 `sys.modules` 中。扫描器在执行前注册临时模块名，执行后清理。

5. **保留 `_ScanEntry` 轻量包装**：虽然启动时间不再约束，但 `_ScanEntry` 作为扫描器的内部类型仍有价值——它只读取 `ScriptEntry` 的字段，不持有对重型模块的引用。

## 后果

### 正面

- 删除 47 个镜像文件 + 1 个辅助文件，消除 shotgun surgery
- 参数定义和 GUI 元数据在同一文件（**locality**）
- 新增轨道类型或参数只需编辑一处
- `test_cli_default_consistency.py` 的意义下降（不再有两处默认值需要同步）
- 扫描器逻辑简化：不再需要镜像目录回退

### 负面

- 实现脚本底部出现 GUI 概念（`CliParam`、`unit_group`、`advanced`）
- 扫描时 import 实现脚本触发重型依赖加载，启动变慢（可通过加载界面缓解）
- 加载失败的脚本被静默跳过，用户可能不知道某个工具不可用（可通过日志或 UI 提示改善）

### 后续

- 可考虑将 `_ScanEntry` 简化为直接使用 `ScriptEntry`（启动时间不再约束）
- 可考虑为加载失败的脚本在 GUI 中显示提示
- `optimize_dro_to_ro.py` 的 e2m2e 依赖缺失问题需要单独修复
