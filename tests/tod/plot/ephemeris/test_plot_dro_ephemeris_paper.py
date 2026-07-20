# pyright: reportArgumentType=false
"""Tests for tod.plot.ephemeris.plot_dro_ephemeris_paper helpers."""

import subprocess
import sys

import pytest


MODULE = "tod.plot.ephemeris.plot_dro_ephemeris_paper"


class TestImportDoesNotPolluteBackend:
    """导入 plot_dro_ephemeris_paper 不应改变进程的 matplotlib 后端。

    GUI 启动时在进程内导入所有注册脚本来读取 SCRIPT_ENTRY（通过
    tod/scripting/scanner.py 的 _load_script_entry）。模块级
    matplotlib.use() 调用会改变 GUI 进程的全局后端，破坏交互式显示。

    本测试用子进程隔离 matplotlib 状态，避免受 conftest.py 的 Agg 干扰。
    """

    def test_import_preserves_interactive_backend(self):
        """设置交互式后端后导入模块，后端不应被改成 Agg。"""
        code = (
            "import matplotlib\n"
            "matplotlib.use('QtAgg')\n"
            "before = matplotlib.get_backend()\n"
            f"import {MODULE}\n"
            "after = matplotlib.get_backend()\n"
            "print(f'{before} {after}')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and "QtAgg" in (result.stderr + result.stdout):
            pytest.skip("QtAgg 不可用，跳过交互式后端测试")
        assert result.returncode == 0, (
            f"子进程异常退出:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        parts = result.stdout.strip().split()
        assert len(parts) == 2, f"输出格式异常: {result.stdout!r}"
        before, after = parts
        assert before == after, (
            f"导入 {MODULE} 后后端从 {before!r} 变为 {after!r}"
        )

    def test_import_preserves_agg_backend(self):
        """已设置 Agg 时导入模块，不应触发 force 切换。"""
        code = (
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
            "before = matplotlib.get_backend()\n"
            f"import {MODULE}\n"
            "after = matplotlib.get_backend()\n"
            "print(f'{before} {after}')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"子进程异常退出:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        parts = result.stdout.strip().split()
        assert len(parts) == 2
        before, after = parts
        assert before == after


class TestParseArgs:
    """parse_args 应接受 argv 列表，允许编程调用和测试。"""

    def test_accepts_out_file_argv(self):
        """传入 --out-file 时应返回对应值。"""
        from tod.plot.ephemeris.plot_dro_ephemeris_paper import parse_args

        args = parse_args(["--out-file", "/tmp/test.png"])
        assert args.out_file == "/tmp/test.png"

    def test_accepts_dpi_argv(self):
        """传入 --dpi 时应返回对应整数值。"""
        from tod.plot.ephemeris.plot_dro_ephemeris_paper import parse_args

        args = parse_args(["--dpi", "600"])
        assert args.dpi == 600

    def test_defaults_when_no_argv(self):
        """不传参数时各选项应返回默认值。"""
        from tod.plot.ephemeris.plot_dro_ephemeris_paper import parse_args

        args = parse_args([])
        assert args.dro_file is None
        assert args.ephemeris_file is None
        assert args.out_file is None
        assert args.dpi == 300

    def test_accepts_all_args(self):
        """同时传入所有参数应正确解析。"""
        from tod.plot.ephemeris.plot_dro_ephemeris_paper import parse_args

        args = parse_args([
            "--dro-file", "/data/dro.json",
            "--ephemeris-file", "/data/eph.json",
            "--out-file", "/output/result.png",
            "--dpi", "150",
        ])
        assert args.dro_file == "/data/dro.json"
        assert args.ephemeris_file == "/data/eph.json"
        assert args.out_file == "/output/result.png"
        assert args.dpi == 150
