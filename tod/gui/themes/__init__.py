"""主题样式表加载。"""

from pathlib import Path

_THEMES_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, str] = {}


def load_stylesheet(theme: str) -> str:
    """加载指定主题的 QSS 样式表，结果缓存于内存。"""
    if theme in _CACHE:
        return _CACHE[theme]
    qss_path = _THEMES_DIR / f"{theme}.qss"
    if not qss_path.is_file():
        return ""
    stylesheet = qss_path.read_text(encoding="utf-8")
    _CACHE[theme] = stylesheet
    return stylesheet
