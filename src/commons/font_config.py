"""CJK 字体回退配置。

CJK font fallback configuration.
"""

from __future__ import annotations


def apply_cjk_font_fallback() -> None:
    """补充中文字体回退到 matplotlib rcParams。

    Add Chinese font fallbacks to the matplotlib rcParams.
    """
    import matplotlib

    cjk_serif_fonts = [
        "Noto Serif CJK SC",
        "Noto Serif CJK JP",
        "Source Han Serif SC",
        "STSong",
        "SimSun",
        "AR PL UMing CN",
    ]
    cjk_sans_fonts = [
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "Noto Sans SC",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "PingFang SC",
        "Hiragino Sans GB",
        "SimHei",
        "WenQuanYi Zen Hei",
    ]
    matplotlib.rcParams["font.serif"] = [
        *cjk_serif_fonts,
        "Times New Roman",
        "DejaVu Serif",
    ]
    matplotlib.rcParams["font.sans-serif"] = [
        *cjk_sans_fonts,
        "DejaVu Sans",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False
