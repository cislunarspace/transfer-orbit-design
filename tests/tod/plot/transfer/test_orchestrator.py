"""Unit tests for tod.plot.transfer.orchestrator shared module."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tod.plot.transfer import orchestrator as orch


# =============================================================================
# TransferPlotConfig
# =============================================================================


class TestTransferPlotConfig:
    def test_default_values(self):
        cfg = orch.TransferPlotConfig()
        assert cfg.direction == ""
        assert cfg.output_subdir == "transfer"
        assert cfg.default_max_points == 50000
        assert cfg.default_dpi == 150

    def test_custom_values(self):
        cfg = orch.TransferPlotConfig(
            direction="DRO→GEO",
            default_search_file="search.json",
            default_max_points=10000,
        )
        assert cfg.direction == "DRO→GEO"
        assert cfg.default_max_points == 10000


# =============================================================================
# build_transfer_argparser
# =============================================================================


class TestBuildTransferArgparser:
    def test_creates_parser_with_common_args(self):
        cfg = orch.TransferPlotConfig(direction="test")
        parser = orch.build_transfer_argparser("Test desc", cfg)
        # Parse known flags
        args = parser.parse_args(["--file", "x.json", "--save", "out.png", "--no-show"])
        assert args.file == "x.json"
        assert args.save == "out.png"
        assert args.no_show is True

    def test_defaults(self):
        cfg = orch.TransferPlotConfig(
            default_max_points=10000, default_dpi=200, default_seed=42
        )
        parser = orch.build_transfer_argparser("Test", cfg)
        args = parser.parse_args([])
        assert args.max_points == 10000
        assert args.dpi == 200
        assert args.seed == 42


# =============================================================================
# load_and_filter_results
# =============================================================================


class TestLoadAndFilterResults:
    def test_list_format(self, tmp_path: Path):
        data = [
            {"alpha": 1.0, "is_feasible": True},
            {"alpha": 2.0, "is_feasible": False},
            {"alpha": 3.0, "is_feasible": True},
        ]
        fpath = tmp_path / "search.json"
        fpath.write_text(json.dumps(data), encoding="utf-8")

        all_rows, feasible = orch.load_and_filter_results(fpath)
        assert len(all_rows) == 3
        assert len(feasible) == 2

    def test_dict_with_results_key(self, tmp_path: Path):
        data = {"meta": {}, "results": [{"is_feasible": True}, {"is_feasible": True}]}
        fpath = tmp_path / "search.json"
        fpath.write_text(json.dumps(data), encoding="utf-8")

        all_rows, feasible = orch.load_and_filter_results(fpath)
        assert len(all_rows) == 2
        assert len(feasible) == 2

    def test_invalid_format(self, tmp_path: Path):
        fpath = tmp_path / "search.json"
        fpath.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        with pytest.raises(ValueError, match="无法识别"):
            orch.load_and_filter_results(fpath)


# =============================================================================
# save_or_show
# =============================================================================


class TestSaveOrShow:
    def test_saves_to_file(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("matplotlib.pyplot.show", lambda: None)
        fig = MagicMock()
        out = tmp_path / "subdir" / "plot.png"

        args = MagicMock()
        args.save = str(out)
        args.dpi = 150
        args.no_show = False

        orch.save_or_show(fig, args)
        assert fig.savefig.called

    def test_shows_when_no_save(self, monkeypatch):
        called = [False]

        def fake_show():
            called[0] = True

        monkeypatch.setattr("matplotlib.pyplot.show", fake_show)
        monkeypatch.setattr("matplotlib.pyplot.close", lambda f: None)
        fig = MagicMock()

        args = MagicMock()
        args.save = None
        args.no_show = False

        orch.save_or_show(fig, args)
        assert called[0]

    def test_no_show_skip(self, monkeypatch):
        called = [False]

        def fake_show():
            called[0] = True

        monkeypatch.setattr("matplotlib.pyplot.show", fake_show)
        monkeypatch.setattr("matplotlib.pyplot.close", lambda f: None)
        fig = MagicMock()

        args = MagicMock()
        args.save = None
        args.no_show = True

        orch.save_or_show(fig, args)
        assert not called[0]


# =============================================================================
# inject_debug_args
# =============================================================================


class TestInjectDebugArgs:
    def test_injects_when_no_args(self):
        argv = ["script.py"]
        orch.inject_debug_args(argv, ["--max-points", "50000"])
        assert argv == ["script.py", "--max-points", "50000"]

    def test_no_inject_when_args_present(self):
        argv = ["script.py", "--file", "x.json"]
        orch.inject_debug_args(argv, ["--file", "other.json"])
        assert argv == ["script.py", "--file", "x.json"]


# =============================================================================
# TransferPlotOrchestrator
# =============================================================================


class TestTransferPlotOrchestrator:
    def test_config_access(self):
        cfg = orch.TransferPlotConfig(direction="DRO→GEO")
        o = orch.TransferPlotOrchestrator(cfg)
        assert o.config.direction == "DRO→GEO"

    def test_project_root(self):
        cfg = orch.TransferPlotConfig()
        o = orch.TransferPlotOrchestrator(cfg)
        root = o.project_root
        assert root.is_dir()
        assert (root / "pyproject.toml").is_file()

    def test_build_parser(self):
        cfg = orch.TransferPlotConfig(direction="test")
        o = orch.TransferPlotOrchestrator(cfg)
        parser = o._build_parser("Test description")
        args = parser.parse_args(["--no-show"])
        assert args.no_show is True

    def test_run_abstract(self):
        cfg = orch.TransferPlotConfig()
        o = orch.TransferPlotOrchestrator(cfg)
        with pytest.raises(NotImplementedError):
            o.run(MagicMock())
