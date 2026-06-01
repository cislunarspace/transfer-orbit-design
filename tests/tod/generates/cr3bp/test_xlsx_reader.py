from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from tod.generates.cr3bp._xlsx_reader import XlsxReadError, read_xlsx_sheets


def _write_minimal_xlsx(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
    <sheet name="Sheet2" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>
""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>x</t></si>
  <si><t>y</t></si>
  <si><t>jacobi</t></si>
  <si><t>Mass ratio</t></si>
</sst>
""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>
    <row r="2"><c r="A2"><v> 1.25</v></c><c r="C2"><v>2.5</v></c></row>
    <row r="3"><c r="A3" t="inlineStr"><is><t>inline</t></is></c><c r="B3"><v>4</v></c><c r="C3"><v>5</v></c></row>
  </sheetData>
</worksheet>
""",
        )
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>3</v></c></row>
    <row r="2"><c r="A2"><v>0.01215</v></c></row>
  </sheetData>
</worksheet>
""",
        )


def test_reads_shared_strings_numeric_cells_inline_strings_and_missing_cells(tmp_path: Path) -> None:
    workbook = tmp_path / "sample.xlsx"
    _write_minimal_xlsx(workbook)

    sheets = read_xlsx_sheets(workbook)

    assert list(sheets) == ["Sheet1", "Sheet2"]
    assert sheets["Sheet1"][0] == ["x", "y", "jacobi"]
    assert sheets["Sheet1"][1] == [" 1.25", "", "2.5"]
    assert sheets["Sheet1"][2] == ["inline", "4", "5"]
    assert sheets["Sheet2"] == [["Mass ratio"], ["0.01215"]]


def test_rejects_invalid_shared_string_index(tmp_path: Path) -> None:
    workbook = tmp_path / "bad-shared-string.xlsx"
    _write_minimal_xlsx(workbook)
    with ZipFile(workbook, "a") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>bad</v></c></row>
  </sheetData>
</worksheet>
""",
        )

    with pytest.raises(XlsxReadError, match="Shared string index is not an integer"):
        read_xlsx_sheets(workbook)