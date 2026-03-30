# 清理 scripts/transfer 目录

## 目标
只保留 grid_search.py、optimize.py、plot_search_results.py 三个文件，删除其余所有文件。

## 任务列表
- [x] 1. 删除 5 个 optimize 依赖模块: optimize_io.py, optimize_nlp.py, optimize_parallel.py, optimize_progress.py, optimize_workers.py
- [x] 2. 删除无关脚本: plot_transfer.py, plot_transfer_results.py
- [x] 3. 删除文档: RUNNING_GUIDE.md, search-optimization-method.md
- [x] 4. 删除 __pycache__ 目录
- [x] 5. 确认最终目录只剩 3 个 .py 文件

## 备注
- optimize.py 导入了被删除的 5 个模块，删除后会暂时无法运行
- 后续通过 create-requirement skill 将这些功能迁移到 e2m2e 库
- plot_optimize_result.py 为后续新建文件，不在本次操作范围内
