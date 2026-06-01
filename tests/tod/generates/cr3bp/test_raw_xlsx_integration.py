from __future__ import annotations

from pathlib import Path

import pytest

from tod.generates.cr3bp.importer import import_cr3bp_xlsx_catalog, load_cr3bp_catalog, normalize_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RAW_DIR = PROJECT_ROOT / "data" / "cr3bp_data" / "raw"


def _require_raw_data(filename: str) -> Path:
    path = RAW_DIR / filename
    if not path.exists():
        pytest.skip(f"raw CR3BP XLSX data not available: {path}")
    return path


def test_reads_real_dro_workbook_metadata_and_row_count() -> None:
    dataset = normalize_workbook(_require_raw_data("earth-moon_dro.xlsx"))

    assert dataset.dataset_id == "earth-moon_dro"
    assert dataset.name.orbit_type == "dro"
    assert len(dataset.records) == 10998
    assert dataset.mu == pytest.approx(1.215058560962404e-02)
    assert dataset.records[0].x == pytest.approx(2.4642189591864819e-02)
    assert dataset.records[0].vy == pytest.approx(7.2237695537238649)
    assert dataset.records[0].jacobi == pytest.approx(1.5410005957354)


def test_reads_real_halo_l1_n_sample_values() -> None:
    dataset = normalize_workbook(_require_raw_data("earth-moon_halo_L1_N.xlsx"))

    assert dataset.dataset_id == "earth-moon_halo_L1_N"
    assert dataset.name.libration_point == "L1"
    assert dataset.name.branch == "N"
    assert dataset.script_status == "supported"
    assert len(dataset.records) == 5731
    first = dataset.records[0]
    assert first.x == pytest.approx(8.7606564511706009e-01)
    assert first.z == pytest.approx(1.9181353568854601e-01)
    assert first.vy == pytest.approx(2.3055753889250671e-01)
    assert first.jacobi == pytest.approx(2.9980180916760499)
    assert first.period == pytest.approx(2.1764730139006754)


def test_imports_all_real_raw_workbooks_to_normalized_catalog(tmp_path: Path) -> None:
    if not RAW_DIR.exists():
        pytest.skip(f"raw CR3BP XLSX data not available: {RAW_DIR}")

    report = import_cr3bp_xlsx_catalog(RAW_DIR, tmp_path / "normalized")
    catalog = load_cr3bp_catalog(report.output_dir)

    assert report.datasets_imported == 42
    assert len(catalog.datasets) == 42
    assert "earth-moon_halo_L3_N" in catalog.datasets
    assert catalog.datasets["earth-moon_halo_L3_N"]["script_status"] == "unsupported_parameter"
    assert "earth-moon_dragonfly_N" in catalog.datasets
    assert catalog.datasets["earth-moon_dragonfly_N"]["script_status"] == "script_missing"
    assert "earth-moon_lpo_E" in catalog.datasets
    assert catalog.datasets["earth-moon_lpo_E"]["script_status"] == "semantic_uncertain"

    halo = catalog.nearest_jacobi("halo", 2.998, libration_point="L1", branch="N", tolerance=1e-3)
    assert halo.dataset_id == "earth-moon_halo_L1_N"
