from __future__ import annotations

import csv
from pathlib import Path
from zipfile import ZipFile

import pytest

from tod.generates.cr3bp.importer import (
    Cr3bpCatalogLookupError,
    Cr3bpImportError,
    Cr3bpImportSchemaError,
    import_cr3bp_xlsx_catalog,
    load_cr3bp_catalog,
    normalize_workbook,
)

SHEET1_COLUMNS = ["x", "y", "z", "vx", "vy", "vz", "jacobi", "period", "stability"]
SHEET2_COLUMNS = ["Mass ratio", "Length unit, LU (km)", "Time unit, TU (s)", "radius_secondary"]


def _xlsx_with_rows(path: Path, sheet1_rows: list[list[str]], sheet2_rows: list[list[str]]) -> None:
    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}

    def shared(value: str) -> int:
        if value not in shared_index:
            shared_index[value] = len(shared_strings)
            shared_strings.append(value)
        return shared_index[value]

    def sheet_xml(rows: list[list[str]]) -> str:
        xml_rows = []
        for row_number, row in enumerate(rows, start=1):
            cells = []
            for column_index, value in enumerate(row, start=1):
                cell_ref = f"{chr(ord('A') + column_index - 1)}{row_number}"
                if row_number == 1:
                    cells.append(f'<c r="{cell_ref}" t="s"><v>{shared(value)}</v></c>')
                else:
                    cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
            xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(xml_rows)}</sheetData>'
            '</worksheet>'
        )

    sheet1_xml = sheet_xml(sheet1_rows)
    sheet2_xml = sheet_xml(sheet2_rows)
    shared_xml = ''.join(f'<si><t>{value}</t></si>' for value in shared_strings)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
            '<sheet name="Sheet2" sheetId="2" r:id="rId2"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="worksheet" Target="worksheets/sheet2.xml"/>'
            '</Relationships>',
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared_xml}</sst>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        archive.writestr("xl/worksheets/sheet2.xml", sheet2_xml)


def _write_cr3bp_workbook(path: Path, rows: list[list[str]] | None = None) -> None:
    _xlsx_with_rows(
        path,
        [
            SHEET1_COLUMNS,
            *(rows or [
                [" 1.0", "2.0", "3.0", "4.0", "5.0", "6.0", "3.1", "7.0", "8.0"],
                ["1.5", "2.5", "3.5", "4.5", "5.5", "6.5", "3.3", "7.5", "8.5"],
            ]),
        ],
        [
            SHEET2_COLUMNS,
            ["0.01215", "389703.0", "382981.0", "1737.1"],
        ],
    )


def test_normalizes_single_workbook_records_and_metadata(tmp_path: Path) -> None:
    workbook = tmp_path / "earth-moon_halo_L1_N.xlsx"
    _write_cr3bp_workbook(workbook)

    dataset = normalize_workbook(workbook)

    assert dataset.dataset_id == "earth-moon_halo_L1_N"
    assert dataset.name.orbit_type == "halo"
    assert dataset.name.libration_point == "L1"
    assert dataset.name.branch == "N"
    assert dataset.script_status == "supported"
    assert dataset.mu == pytest.approx(0.01215)
    assert len(dataset.records) == 2

    first = dataset.records[0]
    assert first.orbit_id == "earth-moon_halo_L1_N:000001"
    assert first.source_row == 2
    assert first.state == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert first.jacobi == pytest.approx(3.1)
    assert first.period == pytest.approx(7.0)
    assert first.stability == pytest.approx(8.0)


def test_rejects_workbook_with_unexpected_sheet1_header(tmp_path: Path) -> None:
    workbook = tmp_path / "earth-moon_dro.xlsx"
    _xlsx_with_rows(
        workbook,
        [["x", "bad"], ["1", "2"]],
        [SHEET2_COLUMNS, ["0.01215", "389703.0", "382981.0", "1737.1"]],
    )

    with pytest.raises(Cr3bpImportSchemaError, match="header mismatch"):
        normalize_workbook(workbook)


def test_rejects_data_rows_with_missing_trailing_columns(tmp_path: Path) -> None:
    workbook = tmp_path / "earth-moon_dro.xlsx"
    _write_cr3bp_workbook(
        workbook,
        rows=[["1", "2", "3", "4", "5", "6", "3.1", "7"]],
    )

    with pytest.raises(Cr3bpImportSchemaError, match="expected 9 columns"):
        normalize_workbook(workbook)


def test_rejects_metadata_rows_with_missing_trailing_values(tmp_path: Path) -> None:
    workbook = tmp_path / "earth-moon_dro.xlsx"
    _xlsx_with_rows(
        workbook,
        [SHEET1_COLUMNS, ["1", "2", "3", "4", "5", "6", "3.1", "7", "8"]],
        [SHEET2_COLUMNS, ["0.01215", "389703.0", "382981.0"]],
    )

    with pytest.raises(Cr3bpImportSchemaError, match="expected 4 columns"):
        normalize_workbook(workbook)


def test_rejects_workbook_with_no_orbit_rows(tmp_path: Path) -> None:
    workbook = tmp_path / "earth-moon_dro.xlsx"
    _xlsx_with_rows(
        workbook,
        [SHEET1_COLUMNS],
        [SHEET2_COLUMNS, ["0.01215", "389703.0", "382981.0", "1737.1"]],
    )

    with pytest.raises(Cr3bpImportSchemaError, match="no orbit data rows"):
        normalize_workbook(workbook)


def test_wraps_invalid_raw_dataset_filename_as_import_error(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_cr3bp_workbook(raw_dir / "halo.xlsx")

    with pytest.raises(Cr3bpImportError, match="Invalid CR3BP raw dataset filename"):
        import_cr3bp_xlsx_catalog(raw_dir, tmp_path / "normalized")


def test_imports_workbooks_to_index_family_csv_and_catalog(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "normalized"
    raw_dir.mkdir()
    _write_cr3bp_workbook(raw_dir / "earth-moon_halo_L1_N.xlsx")
    _write_cr3bp_workbook(raw_dir / "earth-moon_halo_L2_S.xlsx")
    _write_cr3bp_workbook(raw_dir / "earth-moon_dro.xlsx")

    report = import_cr3bp_xlsx_catalog(raw_dir, output_dir)

    assert report.datasets_imported == 3
    assert report.orbits_imported == 6
    assert (output_dir / "index.csv").exists()
    assert (output_dir / "families" / "halo.csv").exists()
    assert (output_dir / "families" / "dro.csv").exists()
    assert (output_dir / "catalog.yaml").exists()

    with (output_dir / "index.csv").open(newline="", encoding="utf-8") as stream:
        index_rows = list(csv.DictReader(stream))
    assert [row["dataset_id"] for row in index_rows] == [
        "earth-moon_dro",
        "earth-moon_halo_L1_N",
        "earth-moon_halo_L2_S",
    ]
    assert {row["script_status"] for row in index_rows} == {"supported"}

    with (output_dir / "families" / "halo.csv").open(newline="", encoding="utf-8") as stream:
        halo_rows = list(csv.DictReader(stream))
    assert len(halo_rows) == 4
    assert {row["dataset_id"] for row in halo_rows} == {
        "earth-moon_halo_L1_N",
        "earth-moon_halo_L2_S",
    }

    catalog_text = (output_dir / "catalog.yaml").read_text(encoding="utf-8")
    assert "schema_version: 1" in catalog_text
    assert "earth-moon_halo_L1_N" in catalog_text


def test_loads_catalog_and_finds_nearest_jacobi_with_filters(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "normalized"
    raw_dir.mkdir()
    _write_cr3bp_workbook(
        raw_dir / "earth-moon_halo_L1_N.xlsx",
        rows=[
            ["0", "0", "0", "0", "0", "0", "3.0", "1", "1"],
            ["1", "0", "0", "0", "0", "0", "3.2", "2", "1"],
        ],
    )
    _write_cr3bp_workbook(
        raw_dir / "earth-moon_halo_L2_S.xlsx",
        rows=[
            ["2", "0", "0", "0", "0", "0", "3.05", "3", "1"],
        ],
    )
    import_cr3bp_xlsx_catalog(raw_dir, output_dir)

    catalog = load_cr3bp_catalog(output_dir)
    nearest = catalog.nearest_jacobi("halo", 3.12, libration_point="L1", branch="N")

    assert nearest.dataset_id == "earth-moon_halo_L1_N"
    assert nearest.jacobi == pytest.approx(3.2)
    assert nearest.state == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    with pytest.raises(Cr3bpCatalogLookupError, match="tolerance"):
        catalog.nearest_jacobi("halo", 3.12, libration_point="L1", branch="N", tolerance=0.01)
