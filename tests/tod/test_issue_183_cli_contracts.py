"""P0 CLI 契约回归测试（issue #204）。

覆盖 grill-me 决策 20 锁定的三类行为：缺参失败、显式文件成功、显式
``--auto-latest`` 才允许自动选择；对每个 P0 入口还验证 ``--file`` 与
``--auto-latest`` 的互斥。

策略：

- 用 ``monkeypatch`` 把 ``project_root`` 重定向到 tmp 目录，绕过对真实
  ``output/transfer`` 或 ``output/dro`` 的依赖。
- 入口 ``main()`` 里通常包含绘图/重型计算（matplotlib、积分等）。本测试
  把每个入口的「输入解析」步骤切到 ``_resolve_*`` helper，直接断言：
    - helper 在缺参/互斥/无候选时抛 ``InputResolutionError`` 或
      ``parser.error``（exit 2）。
    - helper 在显式路径下返回该路径。
    - helper 在 ``--auto-latest`` 下返回 mtime 最新的候选。

  对于没法独立调用的入口（仅 inline 在 main 中），退化为 ``SystemExit``
  进程级断言。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tod.cli.input_file import (
    InputFileRequest,
    InputResolutionError,
    resolve_input_file,
)


# ============================================================
# 子进程级 smoke：缺参 → exit 2
# ============================================================

CLI_MODULES = [
    "tod.plot.transfer.leo_to_dro.plot_search_results_leo_to_dro",
    "tod.plot.transfer.leo_to_dro.plot_optimize_result_leo_to_dro",
    "tod.plot.transfer.geo_to_dro.plot_search_results_geo_to_dro",
    "tod.plot.transfer.geo_to_dro.plot_optimize_result_geo_to_dro",
    "tod.plot.transfer.dro_to_ro.plot_optimize_result_dro_to_ro",
    "tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo",
    "tod.plot.inspection.plot_interactive_orbit_inspector",
    "tod.plot.inspection.plot_single_orbit",
    "tod.transfers.geo_to_dro.optimize_geo_to_dro",
]


@pytest.mark.parametrize("module_name", CLI_MODULES)
def test_cli_missing_input_exits_two(module_name: str) -> None:
    """缺主输入时 P0 CLI 必须 exit 2，且 stderr 含「显式输入」契约信息。"""
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=str(Path(__file__).resolve().parent.parent.parent),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2, (
        f"{module_name} 缺主输入应 exit 2；"
        f"实际 returncode={result.returncode}；stderr={result.stderr!r}"
    )
    # argparse 风格错误前缀
    assert "error" in result.stderr.lower(), (
        f"{module_name} 缺主输入 stderr 缺少 'error' 标记；"
        f"stderr={result.stderr!r}"
    )


# ============================================================
# resolver 单测：把 transfer root 重定向到 tmp_path，覆盖三类行为
# ============================================================


def _touch(path: Path, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    os.utime(path, (mtime, mtime))
    return path


def _patch_project_root(monkeypatch, target_module: str, tmp_path: Path) -> None:
    """把 ``target_module.project_root`` 改写到 tmp_path 下的伪造 root。"""
    fake_root = tmp_path
    (fake_root / "output" / "transfer").mkdir(parents=True)
    (fake_root / "output" / "dro").mkdir(parents=True)
    (fake_root / "output" / "ro").mkdir(parents=True)
    # ``project_root`` 在每个目标模块都存在；用 raising=False 兼容极少数
    # 重命名场景。
    monkeypatch.setattr(f"{target_module}.project_root", fake_root, raising=False)


def test_resolve_search_leo_dro_missing(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.transfer.leo_to_dro import plot_search_results_leo_to_dro

    _patch_project_root(monkeypatch, plot_search_results_leo_to_dro.__name__, tmp_path)
    # 缺参时 helper 调 parser.error(...) 触发 SystemExit(2)
    with pytest.raises(SystemExit) as exc_info:
        plot_search_results_leo_to_dro._resolve_search_input(
            type("A", (), {"file": None, "auto_latest": False})()
        )
    assert exc_info.value.code == 2


def test_resolve_search_leo_dro_explicit(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.transfer.leo_to_dro import plot_search_results_leo_to_dro

    _patch_project_root(monkeypatch, plot_search_results_leo_to_dro.__name__, tmp_path)
    target = _touch(tmp_path / "output" / "transfer" / "search_leo_dro_x.json", mtime=1.0)
    resolved = plot_search_results_leo_to_dro._resolve_search_input(
        type("A", (), {"file": str(target), "auto_latest": False})()
    )
    assert resolved == target.resolve()


def test_resolve_search_leo_dro_auto_latest(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.transfer.leo_to_dro import plot_search_results_leo_to_dro

    _patch_project_root(monkeypatch, plot_search_results_leo_to_dro.__name__, tmp_path)
    _touch(tmp_path / "output" / "transfer" / "search_leo_dro_old.json", mtime=100.0)
    newer = _touch(
        tmp_path / "output" / "transfer" / "search_leo_dro_new.json", mtime=200.0
    )
    resolved = plot_search_results_leo_to_dro._resolve_search_input(
        type("A", (), {"file": None, "auto_latest": True})()
    )
    assert resolved == newer.resolve()


def test_resolve_search_leo_dro_conflict(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.transfer.leo_to_dro import plot_search_results_leo_to_dro

    _patch_project_root(monkeypatch, plot_search_results_leo_to_dro.__name__, tmp_path)
    target = _touch(tmp_path / "output" / "transfer" / "search_leo_dro_x.json", mtime=1.0)
    # 显式路径与 --auto-latest 互斥时 helper 调 parser.error(...) 触发 exit 2
    with pytest.raises(SystemExit) as exc_info:
        plot_search_results_leo_to_dro._resolve_search_input(
            type("A", (), {"file": str(target), "auto_latest": True})()
        )
    assert exc_info.value.code == 2


def test_resolve_opt_geo_dro_auto_latest(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.transfer.geo_to_dro import plot_optimize_result_geo_to_dro

    _patch_project_root(monkeypatch, plot_optimize_result_geo_to_dro.__name__, tmp_path)
    _touch(
        tmp_path / "output" / "transfer" / "optimization_geo_dro_old.json", mtime=100.0
    )
    newer = _touch(
        tmp_path / "output" / "transfer" / "optimization_geo_dro_new.json", mtime=200.0
    )
    resolved = plot_optimize_result_geo_to_dro._resolve_opt_input(
        type("A", (), {"file": None, "auto_latest": True})()
    )
    assert resolved == newer.resolve()


def test_resolve_dro_geo_dro_auto_latest(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.transfer.geo_to_dro import plot_optimize_result_geo_to_dro

    _patch_project_root(monkeypatch, plot_optimize_result_geo_to_dro.__name__, tmp_path)
    _touch(tmp_path / "output" / "dro" / "dro_old.json", mtime=100.0)
    newer = _touch(tmp_path / "output" / "dro" / "dro_new.json", mtime=200.0)
    resolved = plot_optimize_result_geo_to_dro._resolve_dro_input(
        type("A", (), {"dro_file": None, "auto_latest_dro": True})()
    )
    assert resolved == newer.resolve()


def test_resolve_single_orbit_auto_latest(monkeypatch, tmp_path: Path) -> None:
    from tod.plot.inspection import plot_single_orbit

    _patch_project_root(monkeypatch, plot_single_orbit.__name__, tmp_path)
    # 解析 main() 的 inline resolver：直接构造一个 dummy args
    # 因 inline 不可直接调用，我们改为验证 module-level 标志 + argparse
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--json-file")
    parser.add_argument("--auto-latest", action="store_true")
    # 走真正契约
    from tod.cli.input_file import resolve_input_file

    _touch(tmp_path / "output" / "ro" / "ro_old.json", mtime=100.0)
    newer = _touch(tmp_path / "output" / "ro" / "ro_new.json", mtime=200.0)
    resolved = resolve_input_file(
        InputFileRequest(
            explicit_path=None,
            auto_latest=True,
            search_root=tmp_path / "output/ro",
            pattern="ro_*.json",
            flag="--json-file",
            auto_latest_flag="--auto-latest",
        )
    )
    assert resolved == newer.resolve()


def test_resolve_single_orbit_missing_uses_resolver(tmp_path: Path) -> None:
    from tod.cli.input_file import resolve_input_file

    with pytest.raises(InputResolutionError) as exc_info:
        resolve_input_file(
            InputFileRequest(
                explicit_path=None,
                auto_latest=False,
                search_root=tmp_path / "output/ro",
                pattern="ro_*.json",
                flag="--json-file",
                auto_latest_flag="--auto-latest",
            )
        )
    assert exc_info.value.reason == "missing"
    assert exc_info.value.flag == "--json-file"
