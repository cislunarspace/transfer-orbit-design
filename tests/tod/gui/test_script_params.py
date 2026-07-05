# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""脚本参数定义文件的测试。

验证每个实现脚本底部的 SCRIPT_ENTRY：
1. 文件存在且可加载
2. 导出 SCRIPT_ENTRY
3. script_path 指向真实文件
4. cli_param 的 unit_group 和 default_unit 合法
5. 扫描器能发现所有脚本

Run with: pytest tests/tod/gui/test_script_params.py -v
"""

import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 所有期望的脚本（相对于 tod/）
PARAMS_FILES = [
    # Ephemeris — generates/ephemeris/
    "generates/ephemeris/correct_orbit_to_ephemeris.py",
    "generates/ephemeris/correct_dro_family_to_ephemeris.py",
    "generates/ephemeris/correct_halo_family_to_ephemeris.py",
    # generates/cr3bp/
    "generates/cr3bp/dro/generate_dro_orbit.py",
    "generates/cr3bp/dro/generate_dro_family.py",
    "generates/cr3bp/halo/generate_halo_orbit.py",
    "generates/cr3bp/halo/generate_halo_family.py",
    "generates/cr3bp/ro/generate_ro_orbit.py",
    "generates/cr3bp/ro/generate_ro_family.py",
    "generates/cr3bp/dpo/generate_dpo_orbit.py",
    "generates/cr3bp/dpo/generate_dpo_family.py",
    "generates/cr3bp/axial/generate_axial_orbit.py",
    "generates/cr3bp/axial/generate_axial_family.py",
    "generates/cr3bp/butterfly/generate_butterfly_orbit.py",
    "generates/cr3bp/butterfly/generate_butterfly_family.py",
    "generates/cr3bp/horseshoe/generate_horseshoe_orbit.py",
    "generates/cr3bp/horseshoe/generate_horseshoe_family.py",
    "generates/cr3bp/lpo/generate_lpo_orbit.py",
    "generates/cr3bp/lpo/generate_lpo_family.py",
    "generates/cr3bp/lyapunov/generate_lyapunov_orbit.py",
    "generates/cr3bp/lyapunov/generate_lyapunov_family.py",
    "generates/cr3bp/spo/generate_spo_orbit.py",
    "generates/cr3bp/spo/generate_spo_family.py",
    "generates/cr3bp/tadpole/generate_tadpole_orbit.py",
    "generates/cr3bp/tadpole/generate_tadpole_family.py",
    "generates/cr3bp/vertical/generate_vertical_orbit.py",
    "generates/cr3bp/vertical/generate_vertical_family.py",
    # Transfer
    "transfers/dro_to_ro/grid_search_dro_to_ro.py",
    "transfers/dro_to_ro/optimize_dro_to_ro.py",
    "transfers/dro_to_geo/grid_search_dro_to_geo.py",
    "transfers/dro_to_geo/optimize_dro_to_geo.py",
    "transfers/geo_to_dro/grid_search_geo_to_dro.py",
    "transfers/geo_to_dro/optimize_geo_to_dro.py",
    "transfers/geo_to_dro/validate_geo_to_dro.py",
    "transfers/leo_to_dro/grid_search_leo_to_dro.py",
    "transfers/leo_to_dro/optimize_leo_to_dro.py",
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
]


def _load_impl_module(impl_path: Path):
    """用 importlib 加载实现脚本，注册到 sys.modules 避免 @dataclass 问题。"""
    from tod.scripting import _make_module_name

    module_name = _make_module_name(impl_path, "_tod_test")
    spec = importlib.util.spec_from_file_location(module_name, str(impl_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载文件: {impl_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"加载 {impl_path} 时出错: {e}") from e
    finally:
        sys.modules.pop(module_name, None)
    if not hasattr(module, "SCRIPT_ENTRY"):
        raise RuntimeError(f"文件 {impl_path} 缺少 SCRIPT_ENTRY 导出。")
    return module


@pytest.fixture(params=PARAMS_FILES)
def params_file(request) -> Path:
    """Yield each expected params file path."""
    impl = PROJECT_ROOT / "tod" / request.param
    assert impl.is_file(), f"Params file not found: {impl}"
    return impl


@pytest.fixture(params=PARAMS_FILES)
def params_module(request) -> object:
    """Import the params module from the implementation script."""
    impl = PROJECT_ROOT / "tod" / request.param
    if not impl.is_file():
        pytest.skip(f"文件不存在: {impl}")
    try:
        return _load_impl_module(impl)
    except RuntimeError as e:
        # 仅当根因是 ImportError/ModuleNotFoundError（依赖缺失）时跳过
        if isinstance(e.__cause__, (ImportError, ModuleNotFoundError)):
            pytest.skip(f"依赖缺失，跳过: {e.__cause__}")
        raise


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
    from tod.scripting import UNIT_GROUPS

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
    from tod.scripting import UNIT_GROUPS

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


def test_scanner_discovers_all_expected_files() -> None:
    """The scanner must discover every loadable file listed in PARAMS_FILES."""
    from tod.scripting import get_scripts

    scripts = get_scripts()
    scanned_paths = {e.script_path for entries in scripts.values() for e in entries}

    for rel_path in PARAMS_FILES:
        expected = f"tod/{rel_path}"
        if expected in scanned_paths:
            continue
        # 脚本未被发现——可能是导入失败（如依赖缺失）
        # 验证文件确实存在且有 SCRIPT_ENTRY
        impl = PROJECT_ROOT / "tod" / rel_path
        if not impl.is_file():
            pytest.fail(f"文件不存在: {impl}")
        # 尝试加载，如果失败则判断是否为依赖缺失（合法跳过）
        try:
            _load_impl_module(impl)
            pytest.fail(f"Scanner missed loadable script: {expected}")
        except RuntimeError as e:
            if isinstance(e.__cause__, (ImportError, ModuleNotFoundError)):
                pytest.skip(f"依赖缺失，扫描器正确跳过: {expected}")
            raise


# ─── Targeted: plot_ephemeris_correction has --reference-epoch ──────────────────


def test_plot_ephemeris_correction_exposes_reference_epoch_param() -> None:
    """plot_ephemeris_correction GUI entry exposes optional --reference-epoch."""
    file_path = PROJECT_ROOT / "tod" / "plot" / "ephemeris" / "plot_ephemeris_correction.py"
    module = _load_impl_module(file_path)
    flags = [p.flag for p in module.SCRIPT_ENTRY.cli_params]
    assert "--reference-epoch" in flags


def test_load_impl_module_does_not_swallow_code_bugs(tmp_path: Path) -> None:
    """非 ImportError 的异常（如 TypeError）不应被 params_module 逻辑掩盖。

    回归测试：旧实现用字符串匹配 '出错' 判断是否 skip，会把任何 RuntimeError
    都当依赖缺失跳过。新实现检查 __cause__ 是否为 ImportError/ModuleNotFoundError，
    其他异常应正常传播。
    """
    broken = tmp_path / "broken_script.py"
    broken.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class ScriptEntry:\n"
        "    module: str\n"
        "    name: str\n"
        "    description: str\n"
        "    script_path: str\n"
        "# 故意触发 TypeError：调用不存在的方法\n"
        "SCRIPT_ENTRY = object.nonexistent_method()  # type: ignore[attr-defined]\n",
        encoding="utf-8",
    )
    # _load_impl_module 应抛出 RuntimeError，且 __cause__ 不是 ImportError
    with pytest.raises(RuntimeError) as exc_info:
        _load_impl_module(broken)
    assert not isinstance(exc_info.value.__cause__, (ImportError, ModuleNotFoundError)), (
        "非 ImportError 异常不应被当作依赖缺失"
    )
