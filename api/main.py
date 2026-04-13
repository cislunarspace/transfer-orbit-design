"""轨道设计脚本执行 API"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保仓库根目录在 sys.path 中，以导入 scripts 包
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.config import HOST, PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"轨道设计 API 启动: http://{HOST}:{PORT}")
    print(f"仓库根目录: {REPO_ROOT}")
    yield
    # 清理运行中的任务
    from api.runner_service import stop_all_jobs
    stop_all_jobs()


app = FastAPI(
    title="轨道设计脚本执行 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
