"""跨层共享的路径常量。"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

OUTPUT_DIR: Path = _REPO_ROOT / "output"
