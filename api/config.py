"""API 服务配置"""
from pathlib import Path

# 仓库根目录（api/ 的上级）
REPO_ROOT = Path(__file__).resolve().parent.parent

# 脚本输出目录
OUTPUT_DIR = REPO_ROOT / "output"

# FastAPI 服务配置
HOST = "0.0.0.0"
PORT = 8900

# 任务执行配置
MAX_CONCURRENT = 8
JOB_HISTORY_LIMIT = 20
