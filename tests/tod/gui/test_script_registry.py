"""Tests for tod.gui.script_registry."""

from pathlib import Path
import json

import tod
from tod.gui.script_registry import CatalogSeedSelectorParam, SCRIPTS, UNIT_GROUPS

# Project root: parent of the `tod/` package directory.
PROJECT_ROOT = Path(tod.__file__).resolve().parent.parent


def test_all_registered_script_paths_exist() -> None:
    """Every script_path registered in SCRIPTS must point to a real file."""
    missing: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            full_path = PROJECT_ROOT / entry.script_path
            if not full_path.is_file():
                missing.append(f"[{category}] {entry.name}: {entry.script_path}")

    assert not missing, (
        "The following registered script paths do not exist on disk:\n"
        + "\n".join(missing)
    )


def test_dro_single_generator_is_registered_under_new_name() -> None:
    entries = {entry.name: entry for entry in SCRIPTS["generates"]}

    assert "generate_dro_orbit" in entries
    assert "generate_31_dro_orbit" not in entries

    entry = entries["generate_dro_orbit"]
    assert entry.description == "生成 DRO 轨道"
    assert entry.script_path == "tod/generates/cr3bp/dro/generate_dro_orbit.py"


def test_dro_single_generator_exposes_catalog_seed_controls() -> None:
    entry = {entry.name: entry for entry in SCRIPTS["generates"]}["generate_dro_orbit"]
    params = {param.flag: param for param in entry.cli_params}

    assert {"--jacobi", "--seed-id", "--jacobi-tolerance", "--catalog-dir", "--raw-data-dir", "--no-auto-build-catalog"} <= params.keys()
    assert params["--jacobi"].advanced is True
    assert params["--seed-id"].advanced is True
    assert params["--catalog-dir"].advanced is True


def test_dro_single_generator_declares_catalog_seed_selector() -> None:
    entry = {entry.name: entry for entry in SCRIPTS["generates"]}["generate_dro_orbit"]

    assert len(entry.catalog_seed_selectors) == 1
    selector = entry.catalog_seed_selectors[0]
    assert isinstance(selector, CatalogSeedSelectorParam)
    assert selector.key == "dro_catalog_seed"
    assert selector.orbit_type == "dro"
    assert selector.seed_id_flag == "--seed-id"
    assert selector.jacobi_flag == "--jacobi"
    assert selector.manual_flags == ("--x0", "--vy0", "--period")
    assert selector.default_enabled is False


def test_gui_defaults_use_renamed_dro_generator_key() -> None:
    defaults_path = PROJECT_ROOT / "gui_defaults.json"
    defaults = json.loads(defaults_path.read_text(encoding="utf-8"))

    assert "generate_dro_orbit" in defaults
    assert "generate_31_dro_orbit" not in defaults


def test_all_cli_param_unit_groups_are_registered() -> None:
    """每个 CliParam 的 unit_group 都必须存在于 UNIT_GROUPS 中。

    防止注册表里写了 unit_group 但 UNIT_GROUPS 中找不到对应 key，
    导致 GUI 静默跳过单位选择器（参见 dro_to_geo 半径单位 bug）。
    """
    unknown: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            for param in entry.cli_params:
                if param.unit_group is None:
                    continue
                if param.unit_group not in UNIT_GROUPS:
                    unknown.append(
                        f"[{category}] {entry.name} {param.flag}: "
                        f"unit_group={param.unit_group!r} 未在 UNIT_GROUPS 中注册"
                    )

    assert not unknown, "未知的 unit_group:\n" + "\n".join(unknown)


def test_all_cli_param_default_units_are_in_group() -> None:
    """每个 CliParam 的 default_unit 都必须存在于其 unit_group 的单位列表中。"""
    invalid: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            for param in entry.cli_params:
                if param.default_unit is None:
                    continue
                if param.unit_group is None:
                    invalid.append(
                        f"[{category}] {entry.name} {param.flag}: "
                        f"声明了 default_unit={param.default_unit!r} 但 unit_group 为 None"
                    )
                    continue
                group = UNIT_GROUPS.get(param.unit_group)
                if group is None:
                    continue
                if param.default_unit not in group:
                    invalid.append(
                        f"[{category}] {entry.name} {param.flag}: "
                        f"default_unit={param.default_unit!r} 不在 "
                        f"unit_group={param.unit_group!r} 的单位列表 {list(group.keys())} 中"
                    )

    assert not invalid, "无效的 default_unit:\n" + "\n".join(invalid)


def test_ephemeris_conversion_entries_are_grouped_by_orbit_type() -> None:
    entries_by_path = {
        entry.script_path: entry
        for entries in SCRIPTS.values()
        for entry in entries
    }

    expected_paths = {
        "tod/generates/ephemeris/correct_dro_to_ephemeris.py",
        "tod/generates/ephemeris/correct_dro_family_to_ephemeris.py",
        "tod/generates/ephemeris/correct_halo_to_ephemeris.py",
        "tod/generates/ephemeris/correct_halo_family_to_ephemeris.py",
    }

    assert expected_paths <= entries_by_path.keys()


def _ephemeris_conversion_entry(name: str):
    for entry in SCRIPTS["ephemeris"]:
        if entry.name == name:
            return entry
    raise AssertionError(f"Ephemeris entry not registered: {name}")


def test_ephemeris_conversion_entries_expose_required_method_controls() -> None:
    for name in (
        "correct_dro_to_ephemeris",
        "correct_dro_family_to_ephemeris",
        "correct_halo_to_ephemeris",
        "correct_halo_family_to_ephemeris",
    ):
        params = {param.flag: param for param in _ephemeris_conversion_entry(name).cli_params}

        assert params["--input-file"].label == "星历转换输入文件"
        assert params["--reference-epoch"].label == "参考历元"
        assert params["--reference-epoch"].required is True
        assert params["--method"].label == "星历转换方法"
        assert params["--method"].default == "two_level"
        assert params["--method"].choices == ("standard", "two_level", "homotopy")


def test_ephemeris_single_entries_allow_family_selection_by_index() -> None:
    for name in ("correct_dro_to_ephemeris", "correct_halo_to_ephemeris"):
        params = {param.flag: param for param in _ephemeris_conversion_entry(name).cli_params}

        assert "--orbit-index" in params
        assert params["--input-file"].name_pattern is None


def test_ephemeris_family_entries_prefer_family_files_and_expose_family_controls() -> None:
    for name in ("correct_dro_family_to_ephemeris", "correct_halo_family_to_ephemeris"):
        params = {param.flag: param for param in _ephemeris_conversion_entry(name).cli_params}

        assert params["--input-file"].name_pattern == "*_family_*.json"
        assert "--orbit-index" not in params
        assert {"--family-workers", "--fail-fast", "--include-full-trajectory"} <= params.keys()


def test_ephemeris_conversion_entries_expose_advanced_controls() -> None:
    expected_advanced = {
        "--patch-points",
        "--position-tol",
        "--velocity-tol",
        "--spice-kernel-dir",
        "--bodies",
        "--output-file",
        "--per-orbit-workers",
    }

    for name in (
        "correct_dro_to_ephemeris",
        "correct_dro_family_to_ephemeris",
        "correct_halo_to_ephemeris",
        "correct_halo_family_to_ephemeris",
    ):
        params = {param.flag: param for param in _ephemeris_conversion_entry(name).cli_params}

        assert expected_advanced <= params.keys()
        assert all(params[flag].advanced for flag in expected_advanced)
