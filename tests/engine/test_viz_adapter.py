"""tests for src.engine.viz_adapter -- e2m2e 可视化适配层。

验证 view 与 e2m2e OrbitVisualizer 之间的桥接点：CR3BP_System 构造、
地月 / L1-L5 标注绘制、以及 e2m2e 延迟 import 保证 view 层不泄漏。
"""

from __future__ import annotations

import matplotlib
import pytest

matplotlib.use("Agg")


@pytest.fixture()
def qapp():
    """确保 QApplication 存在（与现有 view 测试一致的兜底）。"""
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


_MU = 0.012153645822478  # 地月质量比（issue #339 实测值）


class TestBuildCr3bpSystem:
    def test_build_cr3bp_system_with_mu(self):
        """build_cr3bp_system(mu) 返回 e2m2e CR3BP_System 且 mu 正确。"""
        from src.engine.viz_adapter import build_cr3bp_system

        system = build_cr3bp_system(_MU)
        assert system.mu == pytest.approx(_MU)
        assert system.primary_body == "Earth"
        assert system.secondary_body == "Moon"

    def test_rejects_invalid_mu(self):
        """mu 超出 (0, 0.5) 时应报错（e2m2e 校验）。"""
        from src.engine.viz_adapter import build_cr3bp_system

        with pytest.raises(ValueError):
            build_cr3bp_system(0.9)


class TestDrawPrimaryBodies:
    def test_draw_primary_bodies_3d_adds_artists(self):
        """3D ax 上绘制地月标注后 artist 数量增加。"""
        from matplotlib.figure import Figure

        from src.engine.viz_adapter import draw_primary_bodies

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        before = len(ax.get_children())
        draw_primary_bodies(ax, _MU, is_3d=True)
        assert len(ax.get_children()) > before

    def test_draw_primary_bodies_2d_adds_artists(self):
        """2D ax 上绘制地月标注后 artist 数量增加。"""
        from matplotlib.figure import Figure

        from src.engine.viz_adapter import draw_primary_bodies

        fig = Figure()
        ax = fig.add_subplot(111)
        before = len(ax.get_children())
        draw_primary_bodies(ax, _MU, is_3d=False)
        assert len(ax.get_children()) > before


class TestDrawLibrationPoints:
    def test_draw_libration_points_3d_adds_artists(self):
        """3D ax 上绘制 L1-L5 后 artist 数量增加。"""
        from matplotlib.figure import Figure

        from src.engine.viz_adapter import draw_libration_points

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        before = len(ax.get_children())
        draw_libration_points(ax, _MU, is_3d=True)
        assert len(ax.get_children()) > before

    def test_draw_libration_points_2d_adds_artists(self):
        """2D ax 上绘制 L1-L5 后 artist 数量增加。"""
        from matplotlib.figure import Figure

        from src.engine.viz_adapter import draw_libration_points

        fig = Figure()
        ax = fig.add_subplot(111)
        before = len(ax.get_children())
        draw_libration_points(ax, _MU, is_3d=False)
        assert len(ax.get_children()) > before


class TestNoImportE2m2eAtModuleImport:
    def test_importing_module_does_not_import_e2m2e(self):
        """import src.engine.viz_adapter 不触发 e2m2e 加载（延迟 import）。

        保证 src/view/ 层（经由 adapter 桥接）不泄漏 e2m2e 到 import 期。
        用 subprocess 在干净解释器里验证：既真正测试“全新导入”的属性，
        又不会像 del sys.modules 那样污染当前测试进程、连累后续测试。
        """
        import subprocess
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        script = (
            "import sys; import src.engine.viz_adapter; "
            "leaked = [m for m in sys.modules "
            "if m == 'e2m2e' or m.startswith('e2m2e.')]; "
            "print('LEAKED:' + ','.join(leaked) if leaked else 'CLEAN')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"子进程导入失败 (rc={result.returncode}):\n{result.stderr}"
        )
        assert result.stdout.strip() == "CLEAN", (
            f"viz_adapter 模块级 import 触发了 e2m2e 加载: {result.stdout.strip()}"
        )
