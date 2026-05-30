# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""tod/gui/scripts/ 下脚本参数定义文件的测试。

These tests verify that each params file:
1. Exists and can be imported
2. Exports SCRIPT_ENTRY
3. All script_paths point to real files
4. All cli_param unit_groups and default_units are valid
5. The scanner discovers all expected params files

Run with: pytest tests/tod/gui/test_script_params.py -v
"""

import importlib
import sys
from pathlib import Path

import pytest

import tod

PROJECT_ROOT = Path(tod.__file__).resolve().parent.parent

# All expected params files (relative to tod/gui/scripts/)
PARAMS_FILES = [
    # Ephemeris — generates/ephemeris/
    "generates/ephemeris/dro/correct_dro_to_ephemeris.py",
    "generates/ephemeris/dro/correct_dro_family_to_ephemeris.py",
    "generates/ephemeris/halo/correct_halo_to_ephemeris.py",
    "generates/ephemeris/halo/correct_halo_family_to_ephemeris.py",
    # generates/cr3bp/
    "generates/cr3bp/dro/generate_31_dro_orbit.py",
    "generates/cr3bp/dro/generate_dro_family.py",
    "generates/cr3bp/halo/generate_halo_orbit.py",
    "generates/cr3bp/halo/generate_halo_family.py",
    "generates/cr3bp/ro/deprecated/generate_31_ro_orbit.py",
    "generates/cr3bp/ro/deprecated/generate_31_ro_family.py",
    "generates/cr3bp/ro/deprecated/generate_32_ro_family.py",
    "generates/cr3bp/ro/deprecated/generate_aro_family.py",
    "generates/cr3bp/ro/deprecated/generate_rro_family.py",
    # Transfer
    "transfer/dro_to_ro/grid_search_dro_to_ro.py",
    "transfer/dro_to_ro/optimize_dro_to_ro.py",
    "transfer/dro_to_geo/grid_search_dro_to_geo.py",
    "transfer/dro_to_geo/optimize_dro_to_geo.py",
    "transfer/geo_to_dro/grid_search_geo_to_dro.py",
    "transfer/geo_to_dro/optimize_geo_to_dro.py",
    "transfer/geo_to_dro/validate_geo_to_dro.py",
    "transfer/leo_to_dro/grid_search_leo_to_dro.py",
    "transfer/leo_to_dro/optimize_leo_to_dro.py",
    # Plot
    "plot/plot_orbits.py",
    "plot/ephemeris/plot_ephemeris_correction.py",
    "plot/transfer/dro_to_geo/plot_search_results_dro_to_geo.py",
    "plot/transfer/dro_to_geo/plot_optimize_result_dro_to_geo.py",
    "plot/transfer/dro_to_ro/plot_search_results_dro_to_ro.py",
    "plot/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py",
    "plot/transfer/geo_to_dro/plot_search_results_geo_to_dro.py",
    "plot/transfer/geo_to_dro/plot_optimize_result_geo_to_dro.py",
    "plot/transfer/leo_to_dro/plot_search_results_leo_to_dro.py",
    "plot/transfer/leo_to_dro/plot_optimize_result_leo_to_dro.py",
    "plot/inspection/plot_interactive_orbit_inspector.py",
    "plot/inspection/plot_single_orbit.py",
]


@pytest.fixture(params=PARAMS_FILES)
def params_file(request) -> Path:
    """Yield each expected params file path."""
    scripts_dir = Path(__file__).resolve().parents[3] / "tod" / "gui" / "scripts"
    return scripts_dir / request.param


@pytest.fixture(params=PARAMS_FILES)
def params_module(request, monkeypatch) -> object:
    """Import the params module with proper package context for relative imports."""
    scripts_dir = Path(__file__).resolve().parents[3] / "tod" / "gui" / "scripts"
    file_path = scripts_dir / request.param

    # Compute the package name from the directory structure under scripts_dir.
    # e.g. "generates/ephemeris/dro/x.py" → "tod.gui.scripts.generates.ephemeris.dro"
    rel = file_path.relative_to(scripts_dir)
    pkg_parts = list(rel.parts[:-1])  # drop the filename
    # Prefix with tod.gui.scripts so relative imports resolve against the real package.
    pkg_name = "tod.gui.scripts." + ".".join(pkg_parts)

    # Ensure tod.gui.scripts (root of scripts package tree) is in sys.modules.
    # It may not be present if this fixture runs before any other import touches it.
    if "tod.gui.scripts" not in sys.modules:
        import tod.gui.scripts as _root
        # Override __path__ to point to our scripts/ dir (may be a namespace package).
        _root.__path__ = [str(scripts_dir)]
        sys.modules["tod.gui.scripts"] = _root

    # Set up parent packages so relative imports can resolve.
    # Reuse existing sys.modules entries where available.
    for i in range(len(pkg_parts)):
        parent_name = ".".join(["tod.gui.scripts"] + list(pkg_parts[:i]))
        child_name = pkg_parts[i]
        pkg_full_name = f"{parent_name}.{child_name}"
        pkg_dir = scripts_dir / Path(*pkg_parts[: i + 1])

        if pkg_full_name in sys.modules:
            # Ensure __path__ is set (might be a namespace package without it).
            mod = sys.modules[pkg_full_name]
            if not hasattr(mod, "__path__"):
                mod.__path__ = [str(pkg_dir)]
            continue

        # Create a minimal package and register it.
        pkg = type(sys)(pkg_full_name)
        pkg.__path__ = [str(pkg_dir)]
        pkg.__package__ = parent_name
        sys.modules[pkg_full_name] = pkg

    # Load the target module with its proper package name.
    spec = importlib.util.spec_from_file_location(pkg_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载文件: {file_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"加载 {file_path} 时出错: {e}") from e
    if not hasattr(module, "SCRIPT_ENTRY"):
        raise RuntimeError(
            f"文件 {file_path} 缺少 SCRIPT_ENTRY 导出。"
        )
    return module


# ─── Red: File must exist ────────────────────────────────────────────────────


def test_params_file_exists(params_file: Path) -> None:
    """RED: Each params file must exist on disk."""
    assert params_file.exists(), f"Params file not found: {params_file}"


def test_params_module_exports_script_entry(params_module: object) -> None:
    """RED: Each params module must export SCRIPT_ENTRY."""
    assert hasattr(params_module, "SCRIPT_ENTRY"), (
        f"Module {params_module.__name__} missing SCRIPT_ENTRY export"
    )


# ─── Green: Validate SCRIPT_ENTRY structure ────────────────────────────────────


def test_script_entry_has_required_fields(params_module: object) -> None:
    """SCRIPT_ENTRY must have all required dataclass fields."""
    entry = params_module.SCRIPT_ENTRY
    required = {"module", "name", "description", "script_path"}
    actual = {f.name for f in entry.__dataclass_fields__.values()}
    missing = required - actual
    assert not missing, f"SCRIPT_ENTRY missing fields: {missing}"


def test_script_path_points_to_real_file(params_module: object) -> None:
    """SCRIPT_ENTRY.script_path must point to an existing file."""
    entry = params_module.SCRIPT_ENTRY
    full_path = PROJECT_ROOT / entry.script_path
    assert full_path.is_file(), (
        f"script_path does not exist: {entry.script_path} (resolved to {full_path})"
    )


def test_cli_params_unit_groups_are_registered(params_module: object) -> None:
    """All cli_params with unit_group must reference a key in UNIT_GROUPS."""
    from tod.gui.script_registry import UNIT_GROUPS

    entry = params_module.SCRIPT_ENTRY
    unknown: list[str] = []
    for param in entry.cli_params:
        if param.unit_group is not None and param.unit_group not in UNIT_GROUPS:
            unknown.append(
                f"{entry.name} {param.flag}: unit_group={param.unit_group!r}"
            )
    assert not unknown, "Unknown unit_group:\n" + "\n".join(unknown)


def test_cli_params_default_units_are_in_group(params_module: object) -> None:
    """All cli_params with default_unit must have that unit in their unit_group."""
    from tod.gui.script_registry import UNIT_GROUPS

    entry = params_module.SCRIPT_ENTRY
    invalid: list[str] = []
    for param in entry.cli_params:
        if param.default_unit is None:
            continue
        if param.unit_group is None:
            invalid.append(
                f"{entry.name} {param.flag}: default_unit={param.default_unit!r} but unit_group is None"
            )
            continue
        group = UNIT_GROUPS.get(param.unit_group)
        if group and param.default_unit not in group:
            invalid.append(
                f"{entry.name} {param.flag}: default_unit={param.default_unit!r} "
                f"not in unit_group={param.unit_group!r} units {list(group.keys())}"
            )
    assert not invalid, "Invalid default_unit:\n" + "\n".join(invalid)


# ─── Scanner integration: all expected files are discovered ────────────────────────


def _script_path_from_file(file_path: Path) -> str:
    """Convert a relative file path to script_path format."""
    rel = file_path.relative_to(PROJECT_ROOT)
    return str(rel).replace("\\", "/")


def test_scanner_discovers_all_expected_files() -> None:
    """The scanner must discover every file listed in PARAMS_FILES."""
    from tod.gui.scripts._registry import iter_script_files

    scripts_dir = PROJECT_ROOT / "tod" / "gui" / "scripts"
    # Normalize to forward slashes for cross-platform comparison
    scanned_paths = {str(p.relative_to(scripts_dir)).replace("\\", "/") for p in iter_script_files(scripts_dir)}
    expected_paths = {p.replace("\\", "/") for p in PARAMS_FILES}
    missing = expected_paths - scanned_paths
    assert not missing, f"Scanner missed these params files:\n" + "\n".join(sorted(missing))
