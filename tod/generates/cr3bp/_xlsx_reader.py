"""轻量 XLSX 读取器，仅覆盖 CR3BP 原始数据所需格式。"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import re
import xml.etree.ElementTree as ET


class XlsxReadError(ValueError):
    """XLSX 文件无法读取或结构不受支持。"""


_CELL_REF_RE = re.compile(r"([A-Z]+)(\d+)")
_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def read_xlsx_sheets(path: Path) -> dict[str, list[list[str]]]:
    """读取 workbook 中所有工作表，返回 sheet 名到二维字符串表的映射。"""

    try:
        with ZipFile(path) as archive:
            shared_strings = _read_shared_strings(archive)
            sheet_paths = _read_sheet_paths(archive)
            return {
                sheet_name: _read_sheet_rows(archive, sheet_path, shared_strings)
                for sheet_name, sheet_path in sheet_paths.items()
            }
    except KeyError as exc:
        raise XlsxReadError(f"Unsupported XLSX structure in {path}: missing {exc}") from exc


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("main:si", _NS):
        text_parts = [node.text or "" for node in item.findall(".//main:t", _NS)]
        strings.append("".join(text_parts))
    return strings


def _read_sheet_paths(archive: ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))

    rel_targets = {
        rel.attrib["Id"]: _normalize_sheet_target(rel.attrib["Target"])
        for rel in rels.findall("pkgrel:Relationship", _NS)
    }

    sheet_paths: dict[str, str] = {}
    for sheet in workbook.findall("main:sheets/main:sheet", _NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib[f"{{{_NS['rel']}}}id"]
        if rel_id not in rel_targets:
            raise XlsxReadError(f"Workbook sheet {name!r} references unknown relationship {rel_id!r}")
        sheet_paths[name] = rel_targets[rel_id]
    return sheet_paths


def _normalize_sheet_target(target: str) -> str:
    cleaned = target.lstrip("/")
    if cleaned.startswith("xl/"):
        return cleaned
    return f"xl/{cleaned}"


def _read_sheet_rows(
    archive: ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []

    for row in root.findall(".//main:sheetData/main:row", _NS):
        values_by_col: dict[int, str] = {}
        max_col = 0
        for cell in row.findall("main:c", _NS):
            column_index = _cell_column_index(cell.attrib.get("r", ""))
            max_col = max(max_col, column_index)
            values_by_col[column_index] = _cell_text(cell, shared_strings)
        rows.append([values_by_col.get(col, "") for col in range(1, max_col + 1)])
    return rows


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value = cell.findtext("main:v", default="", namespaces=_NS)
        if value == "":
            return ""
        try:
            index = int(value)
        except ValueError as exc:
            raise XlsxReadError(f"Shared string index is not an integer: {value!r}") from exc
        try:
            return shared_strings[index]
        except IndexError as exc:
            raise XlsxReadError(f"Shared string index out of range: {index}") from exc

    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", _NS))

    return cell.findtext("main:v", default="", namespaces=_NS)


def _cell_column_index(cell_ref: str) -> int:
    match = _CELL_REF_RE.fullmatch(cell_ref)
    if not match:
        raise XlsxReadError(f"Cell reference is missing or invalid: {cell_ref!r}")

    column_name = match.group(1)
    index = 0
    for char in column_name:
        index = index * 26 + ord(char) - ord("A") + 1
    return index
