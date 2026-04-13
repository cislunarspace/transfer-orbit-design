"""文件发现 API — 列出 output/ 目录下的文件"""
from fastapi import APIRouter, Query

from api.models import FileInfoSchema
from api.config import OUTPUT_DIR

router = APIRouter()


@router.get("/files", response_model=list[FileInfoSchema])
async def list_files(
    category: str | None = Query(None, description="按分类过滤 (dro/ro/halo/transfer/ephemeris)"),
    file_type: str | None = Query("json", description="按扩展名过滤"),
):
    """列出可用的输出文件"""
    from scripts.gui.file_discovery import discover_files, filter_files

    all_files = discover_files(OUTPUT_DIR.parent)
    filtered = filter_files(all_files, category=category, file_type=file_type)

    result = []
    for f in filtered:
        modified = f.modified
        if hasattr(modified, 'isoformat'):
            modified = modified.isoformat()
        result.append(FileInfoSchema(
            name=f.name,
            path=f.path,
            size=f.size,
            modified=str(modified),
            file_type=f.file_type,
            category=f.category,
        ))
    return result
