"""轨道设计脚本执行 API"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("orbit_api")

# 确保仓库根目录在 sys.path 中，以导入 scripts 包
from api.config import HOST, PORT, REPO_ROOT  # noqa: E402

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("轨道设计 API 启动: http://%s:%s", HOST, PORT)
    logger.info("仓库根目录: %s", REPO_ROOT)
    yield
    # 清理运行中的任务
    from api.runner_service import stop_all_jobs
    stop_all_jobs()


app = FastAPI(
    title="轨道设计脚本执行 API",
    version="1.0.0",
    lifespan=lifespan,
)

# [FIX] CORS: 限制允许的来源，不再使用 allow_origins=["*"] + allow_credentials=True
from api.config import ALLOWED_ORIGINS  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from api.registry_service import router as registry_router  # noqa: E402
from api.file_service import router as file_router  # noqa: E402
from api.runner_service import router as runner_router  # noqa: E402

app.include_router(registry_router, prefix="/api", tags=["registry"])
app.include_router(file_router, prefix="/api", tags=["files"])
app.include_router(runner_router, prefix="/api", tags=["runner"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=HOST, port=PORT, reload=True)
