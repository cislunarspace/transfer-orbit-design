"""API 服务配置"""
import logging
from collections import deque
from pathlib import Path

# 日志配置
logger = logging.getLogger("orbit_api")

# 仓库根目录（api/ 的上级）
REPO_ROOT = Path(__file__).resolve().parent.parent

# 脚本输出目录
OUTPUT_DIR = REPO_ROOT / "output"

# FastAPI 服务配置
HOST = "0.0.0.0"
PORT = 8900

# 允许的前端来源 (生产 + 开发)
ALLOWED_ORIGINS = [
    "https://cislunarspace.cn",
    "https://www.cislunarspace.cn",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
]

# 任务执行配置
MAX_CONCURRENT = 8
JOB_HISTORY_LIMIT = 20
MAX_JOB_SECONDS = 3600  # 单任务最大运行时间 (秒)
