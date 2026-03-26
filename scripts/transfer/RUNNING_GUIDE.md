## 运行方式

### 1. 安装 e2m2e 依赖库

在 `e2m2e` 项目根目录下执行：

```bash
python -m pip install -e .
```

这将以**开发模式**安装 e2m2e 库，使修改后的代码立即生效。

### 2. 安装项目依赖

在 `transfer-orbit-design` 项目根目录下执行：

```bash
python -m pip install -r requirements
```

### 3. 生成轨道数据

依次运行以下两个脚本，生成初始轨道（发射轨道）和目标轨道数据：

```bash
python scripts/generate/generate_31_dro_orbit.py
python scripts/generate/generate_31_ro_orbit.py
```

> 运行后，轨道数据将自动保存至 `transfer-orbit-design/output/dro/` 和 `transfer-orbit-design/output/ro/` 目录。

### 4. 配置轨道数据路径

打开 `transfer-orbit-design/scripts/transfer/grid_search.py`，在"参数配置"区域修改轨道数据文件路径为实际生成的文件名：

```python
# 轨道数据文件路径（相对本仓库根目录；与当前工作目录无关）
DRO_FILE = project_root / "output/dro/dro_31_3857337599.json"
RO_FILE = project_root / "output/ro/ro_31_3857337606.json"
```

> 请将上述文件名替换为第 3 步实际生成的文件名（文件名中包含时间戳）。

### 5. 设置搜索参数

在同一文件中设置以下参数：

```python
N_ALPHA = 1001
MAX_TRANSFER_TIME = 200.0 / TU
```

### 6. 执行网格搜索

```bash
python scripts/transfer/grid_search.py
```
