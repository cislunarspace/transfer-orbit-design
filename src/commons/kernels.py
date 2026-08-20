"""SPICE 内核下载与可用性判断。

内核资产托管在 e2m2e 的 GitHub Release ``kernels-v1``（国内网络可达；
NAIF 官方源常不可达），不随 pip 包分发，需宿主项目自行准备。本模块提供：

- ``download_kernels``：幂等拉取 release 全部内核到指定目录（可带进度回调）
- ``kernel_dir_usable``：目录是否含轨道设计所需内核（行星历 ``.bsp`` + 闰秒 ``.tls``）
- ``user_kernel_dir``：用户数据目录下的默认内核位置（pip 安装场景的落点）

调用方：
- ``scripts/download_kernels.py``：CLI 包装（源码用户手动补齐内核）
- ``src/app/kernel_setup.py``：GUI 首次启动引导（弹窗确认 → 下载带进度条 /
  指定已有目录）
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable

REPO = "cislunarspace/e2m2e"
RELEASE = "kernels-v1"

#: 下载源域名白名单（SSRF 防线）：API 清单与 release 资产只从 GitHub 官方域拉取
_ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "api.github.com",
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)
# release 同款 pattern：星历/闰秒/常数/姿态/帧
EXTENSIONS = (".bsp", ".tls", ".tpc", ".bpc", ".tf")
# load_design_kernels 认 de440s/de430；find_ephemeris_kernel 另收 de440/de435/de438。
# 宽松判断：以上任一存在即视为有行星历。
_EPHEMERIS_NAMES = ("de440.bsp", "de440s.bsp", "de435.bsp", "de438.bsp", "de430.bsp")
# 模块级常量（测试可替换），避免运行时改全局 os.name
_IS_WINDOWS = os.name == "nt"


def user_kernel_dir() -> pathlib.Path:
    """用户数据目录下的默认内核位置（跨版本共享，升级不重下）。

    Windows 用 ``%LOCALAPPDATA%``，其余平台用 XDG 数据目录（默认
    ``~/.local/share``）。
    """
    if _IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or pathlib.Path.home() / "AppData" / "Local"
    else:
        base = os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    return pathlib.Path(base) / "transfer-orbit-design" / "kernels"


def _api_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _check_download_url(url: str) -> None:
    """校验下载 URL 为 https 且域名在白名单。

    资产 URL 来自 GitHub API 响应（非用户输入，但属外部数据）。urlopen
    会自动跟随重定向，故调用方须在 urlopen 前校验初始 URL、在打开后用
    ``resp.geturl()`` 再校验重定向终点。
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_DOWNLOAD_HOSTS:
        raise ValueError(f"下载源不在白名单: {url}")


def list_release_assets() -> list[dict]:
    """列 ``kernels-v1`` release 的全部资产（name + browser_download_url）。"""
    url = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE}"
    # 对本函数拼出的字面量也校验：与 _download 对称的纵深防御
    _check_download_url(url)
    req = urllib.request.Request(url, headers=_api_headers())
    with urllib.request.urlopen(req) as resp:  # noqa: S310 — 初始与终点 URL 均过白名单
        _check_download_url(resp.geturl())
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("assets", [])


def _download(url: str, dest: pathlib.Path) -> None:
    _check_download_url(url)
    print(f"下载 {url} → {dest}", file=sys.stderr)
    # 流式分块写盘，避免百 MB 级 .bsp 整块驻留内存
    with urllib.request.urlopen(url) as resp, dest.open("wb") as fh:  # noqa: S310 — 初始与终点 URL 均过白名单
        # 首个 chunk 写盘前校验重定向终点，不通过则不落任何数据
        _check_download_url(resp.geturl())
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)


def download_kernels(
    kernel_dir: pathlib.Path,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int]:
    """拉取 ``kernels-v1`` 全部内核到 ``kernel_dir``（幂等：已存在跳过）。

    Args:
        kernel_dir: 目标目录（不存在则创建）。
        progress: 每处理完一个文件回调 ``(done, total, name)``；total 为
            release 资产总数，跳过与下载都计入 done。

    Returns:
        ``(fetched, skipped)``。
    """
    kernel_dir = pathlib.Path(kernel_dir)
    kernel_dir.mkdir(parents=True, exist_ok=True)

    assets = list_release_assets()
    targets = [a for a in assets if a["name"].lower().endswith(EXTENSIONS)]
    if not targets:
        raise RuntimeError(f"release {RELEASE} 未找到内核资产（扩展名 {EXTENSIONS}）")

    fetched = 0
    skipped = 0
    total = len(targets)
    for i, asset in enumerate(targets, start=1):
        dest = kernel_dir / asset["name"]
        if dest.is_file():
            skipped += 1
        else:
            _download(asset["browser_download_url"], dest)
            fetched += 1
        if progress is not None:
            progress(i, total, asset["name"])
    return fetched, skipped


def kernel_dir_usable(kernel_dir: str | os.PathLike[str]) -> bool:
    """目录是否含轨道设计所需内核：行星历（de440s/de430 等 .bsp）＋闰秒（.tls）。

    缺任一即不可用：无行星历则 ``design_orbit`` 直接报错；无闰秒则
    UTC↔ET 转换失败（SPICE NOLEAPSECONDS）。
    """
    d = pathlib.Path(kernel_dir)
    if not d.is_dir():
        return False
    names = {f.name for f in d.iterdir() if f.is_file()}
    return any(n in _EPHEMERIS_NAMES for n in names) and any(n.endswith(".tls") for n in names)
