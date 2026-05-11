# Development Guide

## Logging vs Print

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
