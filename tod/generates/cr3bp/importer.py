"""CR3BP 原始 XLSX 轨道数据导入与 normalized catalog 查询。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import csv
import sys

from tod.generates.cr3bp._raw_naming import RawDatasetName, RawDatasetNameError, parse_raw_xlsx_name
from tod.generates.cr3bp._xlsx_reader import XlsxReadError, read_xlsx_sheets


SHEET1_COLUMNS = ["x", "y", "z", "vx", "vy", "vz", "jacobi", "period", "stability"]
SHEET2_COLUMNS = ["Mass ratio", "Length unit, LU (km)", "Time unit, TU (s)", "radius_secondary"]

ORBIT_FIELDNAMES = [
    "orbit_id",
    "dataset_id",
    "system",
    "source_orbit_type",
    "orbit_type",
    "variant",
    "libration_point",
    "branch",
    "resonance",
    "source_file",
    "source_row",
    "x",
    "y",
    "z",
    "vx",
    "vy",
    "vz",
    "jacobi",
    "period",
    "stability",
    "mu",
    "length_unit_km",
    "time_unit_s",
    "radius_secondary",
    "script_status",
]

INDEX_FIELDNAMES = [
    "dataset_id",
    "system",
    "source_orbit_type",
    "orbit_type",
    "variant",
    "libration_point",
    "branch",
    "resonance",
    "source_file",
    "family_csv",
    "row_count",
    "jacobi_min",
    "jacobi_max",
    "period_min",
    "period_max",
    "stability_min",
    "stability_max",
    "mu",
    "length_unit_km",
    "time_unit_s",
    "radius_secondary",
    "script_status",
]


class Cr3bpImportError(ValueError):
    """CR3BP 数据导入失败。"""


class Cr3bpImportSchemaError(Cr3bpImportError):
    """原始 XLSX 数据结构与预期 schema 不一致。"""


class Cr3bpCatalogLookupError(LookupError):
    """normalized catalog 中找不到满足条件的轨道。"""


@dataclass(frozen=True)
class OrbitRecord:
    """normalized 后的一条轨道初值记录。"""

    orbit_id: str
    dataset_id: str
    system: str
    source_orbit_type: str
    orbit_type: str
    variant: str
    libration_point: str
    branch: str
    resonance: str
    source_file: str
    source_row: int
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    jacobi: float
    period: float
    stability: float
    mu: float
    length_unit_km: float
    time_unit_s: float
    radius_secondary: float
    script_status: str

    @property
    def state(self) -> list[float]:
        return [self.x, self.y, self.z, self.vx, self.vy, self.vz]


@dataclass(frozen=True)
class DatasetRecord:
    """一个原始 workbook 规范化后的数据集。"""

    name: RawDatasetName
    records: list[OrbitRecord]
    mu: float
    length_unit_km: float
    time_unit_s: float
    radius_secondary: float
    script_status: str

    @property
    def dataset_id(self) -> str:
        return self.name.dataset_id


@dataclass(frozen=True)
class ImportReport:
    raw_dir: Path
    output_dir: Path
    datasets_imported: int
    orbits_imported: int
    index_file: Path
    catalog_file: Path
    family_files: dict[str, Path]


class Cr3bpCatalog:
    """从 normalized CSV 加载的 CR3BP 初值 catalog。"""

    def __init__(self, datasets: dict[str, dict[str, str]], records: list[OrbitRecord]) -> None:
        self.datasets = datasets
        self._records = records

    def records(self, *, orbit_type: str | None = None) -> list[OrbitRecord]:
        if orbit_type is None:
            return list(self._records)
        return [record for record in self._records if record.orbit_type == orbit_type]

    def nearest_jacobi(
        self,
        orbit_type: str,
        jacobi: float,
        *,
        dataset_id: str | None = None,
        libration_point: str | None = None,
        branch: str | None = None,
        resonance: str | None = None,
        tolerance: float | None = None,
    ) -> OrbitRecord:
        candidates = [record for record in self._records if record.orbit_type == orbit_type]
        if dataset_id is not None:
            candidates = [record for record in candidates if record.dataset_id == dataset_id]
        if libration_point is not None:
            candidates = [record for record in candidates if record.libration_point == libration_point]
        if branch is not None:
            candidates = [record for record in candidates if record.branch == branch]
        if resonance is not None:
            candidates = [record for record in candidates if record.resonance == resonance]

        if not candidates:
            raise Cr3bpCatalogLookupError(f"No CR3BP catalog records match orbit_type={orbit_type!r}")

        nearest = min(candidates, key=lambda record: (abs(record.jacobi - jacobi), record.dataset_id, record.source_row))
        if tolerance is not None and abs(nearest.jacobi - jacobi) > tolerance:
            raise Cr3bpCatalogLookupError(
                "Nearest Jacobi record exceeds tolerance: "
                f"target={jacobi}, actual={nearest.jacobi}, "
                f"error={abs(nearest.jacobi - jacobi)}, tolerance={tolerance}"
            )
        return nearest


def normalize_workbook(path: Path) -> DatasetRecord:
    """将一个原始 CR3BP XLSX workbook 规范化为内存记录。"""

    try:
        name = parse_raw_xlsx_name(path)
        sheets = read_xlsx_sheets(path)
    except RawDatasetNameError as exc:
        raise Cr3bpImportError(f"Invalid CR3BP raw dataset filename {path.name}: {exc}") from exc
    except XlsxReadError as exc:
        raise Cr3bpImportSchemaError(f"Cannot read CR3BP raw workbook {path.name}: {exc}") from exc

    data_rows = _require_sheet(sheets, "Sheet1", path)
    metadata_rows = _require_sheet(sheets, "Sheet2", path)
    _validate_header(data_rows, SHEET1_COLUMNS, path, "Sheet1")
    _validate_header(metadata_rows, SHEET2_COLUMNS, path, "Sheet2")

    metadata = _metadata_from_rows(metadata_rows, path)
    script_status = script_status_for(name)
    records = [
        _record_from_row(name, row, source_row, metadata, script_status)
        for source_row, row in enumerate(data_rows[1:], start=2)
        if any(cell.strip() for cell in row)
    ]
    if not records:
        raise Cr3bpImportSchemaError(f"{path.name}:Sheet1 contains no orbit data rows")

    return DatasetRecord(
        name=name,
        records=records,
        mu=metadata["mu"],
        length_unit_km=metadata["length_unit_km"],
        time_unit_s=metadata["time_unit_s"],
        radius_secondary=metadata["radius_secondary"],
        script_status=script_status,
    )


def import_cr3bp_xlsx_catalog(raw_dir: Path, output_dir: Path, *, overwrite: bool = False) -> ImportReport:
    """导入 raw_dir 下全部 CR3BP XLSX，写出 normalized CSV 与 catalog.yaml。"""

    if not raw_dir.exists() or not raw_dir.is_dir():
        raise Cr3bpImportError(f"Raw CR3BP data directory does not exist: {raw_dir}")

    xlsx_files = sorted(path for path in raw_dir.glob("*.xlsx") if path.is_file())
    if not xlsx_files:
        raise Cr3bpImportError(f"No CR3BP XLSX files found in: {raw_dir}")

    managed_targets = [output_dir / "index.csv", output_dir / "catalog.yaml"]
    if output_dir.exists() and not overwrite:
        existing_managed = [path for path in managed_targets if path.exists()]
        families_dir = output_dir / "families"
        if families_dir.exists():
            existing_managed.extend(sorted(families_dir.glob("*.csv")))
        if existing_managed:
            raise Cr3bpImportError(f"Normalized output already exists: {existing_managed[0]}")

    datasets = [normalize_workbook(path) for path in xlsx_files]
    output_dir.mkdir(parents=True, exist_ok=True)
    families_dir = output_dir / "families"
    families_dir.mkdir(parents=True, exist_ok=True)

    family_files = _write_family_csvs(datasets, families_dir)
    _write_index_csv(datasets, output_dir / "index.csv", family_files)
    _write_catalog_yaml(datasets, output_dir / "catalog.yaml", family_files)

    return ImportReport(
        raw_dir=raw_dir,
        output_dir=output_dir,
        datasets_imported=len(datasets),
        orbits_imported=sum(len(dataset.records) for dataset in datasets),
        index_file=output_dir / "index.csv",
        catalog_file=output_dir / "catalog.yaml",
        family_files=family_files,
    )


def load_cr3bp_catalog(data_dir: Path) -> Cr3bpCatalog:
    """从 normalized CSV 加载 CR3BP catalog。"""

    index_file = data_dir / "index.csv"
    if not index_file.exists():
        raise Cr3bpImportError(f"Normalized CR3BP index.csv not found: {index_file}")

    with index_file.open(newline="", encoding="utf-8") as stream:
        index_rows = list(csv.DictReader(stream))

    datasets = {row["dataset_id"]: row for row in index_rows}
    family_paths = sorted({data_dir / row["family_csv"] for row in index_rows})
    records: list[OrbitRecord] = []
    for family_path in family_paths:
        if not family_path.exists():
            raise Cr3bpImportError(f"Normalized CR3BP family CSV not found: {family_path}")
        with family_path.open(newline="", encoding="utf-8") as stream:
            records.extend(_orbit_record_from_csv_row(row) for row in csv.DictReader(stream))

    return Cr3bpCatalog(datasets, records)


def script_status_for(name: RawDatasetName) -> str:
    if name.orbit_type == "dro":
        return "supported"
    if name.orbit_type == "halo" and name.libration_point in {"L1", "L2"}:
        return "supported"
    if name.orbit_type == "halo" and name.libration_point == "L3":
        return "unsupported_parameter"
    if name.orbit_type == "resonant" and name.resonance not in {"21", "31", "32"}:
        return "unsupported_parameter"
    if name.orbit_type in {"dragonfly"}:
        return "script_missing"
    if name.orbit_type in {"lpo_directional"}:
        return "semantic_uncertain"
    return "script_incomplete"


def _require_sheet(sheets: dict[str, list[list[str]]], name: str, path: Path) -> list[list[str]]:
    if name not in sheets:
        raise Cr3bpImportSchemaError(f"{path.name} is missing required sheet {name}")
    return sheets[name]


def _validate_header(rows: list[list[str]], expected: list[str], path: Path, sheet: str) -> None:
    if not rows:
        raise Cr3bpImportSchemaError(f"{path.name}:{sheet} is empty")
    header = [cell.strip() for cell in rows[0]]
    if header != expected:
        raise Cr3bpImportSchemaError(
            f"{path.name}:{sheet} header mismatch: expected {expected}, got {header}"
        )


def _validate_row_width(row: list[str], expected_columns: list[str], path: Path, sheet: str, row_number: int) -> None:
    if len(row) < len(expected_columns):
        raise Cr3bpImportSchemaError(
            f"{path.name}:{sheet}:{row_number} has {len(row)} cells; "
            f"expected {len(expected_columns)} columns {expected_columns}"
        )


def _metadata_from_rows(rows: list[list[str]], path: Path) -> dict[str, float]:
    if len(rows) < 2:
        raise Cr3bpImportSchemaError(f"{path.name}:Sheet2 is missing metadata values")
    values = rows[1]
    _validate_row_width(values, SHEET2_COLUMNS, path, "Sheet2", 2)
    return {
        "mu": _parse_float(values[0], path=path, sheet="Sheet2", row=2, column="Mass ratio"),
        "length_unit_km": _parse_float(values[1], path=path, sheet="Sheet2", row=2, column="Length unit, LU (km)"),
        "time_unit_s": _parse_float(values[2], path=path, sheet="Sheet2", row=2, column="Time unit, TU (s)"),
        "radius_secondary": _parse_float(values[3], path=path, sheet="Sheet2", row=2, column="radius_secondary"),
    }


def _record_from_row(
    name: RawDatasetName,
    row: list[str],
    source_row: int,
    metadata: dict[str, float],
    script_status: str,
) -> OrbitRecord:
    _validate_row_width(row, SHEET1_COLUMNS, Path(name.source_file), "Sheet1", source_row)
    values = {
        column: _parse_float(row[index], path=Path(name.source_file), sheet="Sheet1", row=source_row, column=column)
        for index, column in enumerate(SHEET1_COLUMNS)
    }
    return OrbitRecord(
        orbit_id=f"{name.dataset_id}:{source_row - 1:06d}",
        dataset_id=name.dataset_id,
        system=name.system,
        source_orbit_type=name.source_orbit_type,
        orbit_type=name.orbit_type,
        variant=name.variant,
        libration_point=name.libration_point,
        branch=name.branch,
        resonance=name.resonance,
        source_file=name.source_file,
        source_row=source_row,
        x=values["x"],
        y=values["y"],
        z=values["z"],
        vx=values["vx"],
        vy=values["vy"],
        vz=values["vz"],
        jacobi=values["jacobi"],
        period=values["period"],
        stability=values["stability"],
        mu=metadata["mu"],
        length_unit_km=metadata["length_unit_km"],
        time_unit_s=metadata["time_unit_s"],
        radius_secondary=metadata["radius_secondary"],
        script_status=script_status,
    )


def _parse_float(value: str, *, path: Path, sheet: str, row: int, column: str) -> float:
    stripped = value.strip()
    if not stripped:
        raise Cr3bpImportSchemaError(f"{path.name}:{sheet}:{row}:{column} is empty")
    try:
        return float(stripped)
    except ValueError as exc:
        raise Cr3bpImportSchemaError(
            f"{path.name}:{sheet}:{row}:{column} is not a float: {value!r}"
        ) from exc


def _write_family_csvs(datasets: list[DatasetRecord], families_dir: Path) -> dict[str, Path]:
    by_type: dict[str, list[OrbitRecord]] = {}
    for dataset in datasets:
        by_type.setdefault(dataset.name.orbit_type, []).extend(dataset.records)

    family_files: dict[str, Path] = {}
    for orbit_type, records in sorted(by_type.items()):
        path = families_dir / f"{orbit_type}.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=ORBIT_FIELDNAMES)
            writer.writeheader()
            for record in records:
                writer.writerow(_orbit_record_to_csv_row(record))
        family_files[orbit_type] = path
    return family_files


def _write_index_csv(
    datasets: list[DatasetRecord],
    index_file: Path,
    family_files: dict[str, Path],
) -> list[dict[str, str]]:
    rows = [_index_row(dataset, family_files[dataset.name.orbit_type]) for dataset in datasets]
    with index_file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_catalog_yaml(
    datasets: list[DatasetRecord],
    catalog_file: Path,
    family_files: dict[str, Path],
) -> None:
    lines = [
        "schema_version: 1",
        "generated_by: tod.generates.cr3bp.importer",
        "files:",
        "  index: index.csv",
        "  families:",
    ]
    for orbit_type, path in sorted(family_files.items()):
        lines.append(f"    {orbit_type}: families/{path.name}")
    lines.append("datasets:")
    for dataset in datasets:
        lines.extend(
            [
                f"  - dataset_id: {dataset.dataset_id}",
                f"    orbit_type: {dataset.name.orbit_type}",
                f"    source_orbit_type: {dataset.name.source_orbit_type}",
                f"    source_file: {dataset.name.source_file}",
                f"    row_count: {len(dataset.records)}",
                f"    script_status: {dataset.script_status}",
            ]
        )
    catalog_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _index_row(dataset: DatasetRecord, family_file: Path) -> dict[str, str]:
    jacobis = [record.jacobi for record in dataset.records]
    periods = [record.period for record in dataset.records]
    stabilities = [record.stability for record in dataset.records]
    return {
        "dataset_id": dataset.dataset_id,
        "system": dataset.name.system,
        "source_orbit_type": dataset.name.source_orbit_type,
        "orbit_type": dataset.name.orbit_type,
        "variant": dataset.name.variant,
        "libration_point": dataset.name.libration_point,
        "branch": dataset.name.branch,
        "resonance": dataset.name.resonance,
        "source_file": dataset.name.source_file,
        "family_csv": f"families/{family_file.name}",
        "row_count": str(len(dataset.records)),
        "jacobi_min": str(min(jacobis)),
        "jacobi_max": str(max(jacobis)),
        "period_min": str(min(periods)),
        "period_max": str(max(periods)),
        "stability_min": str(min(stabilities)),
        "stability_max": str(max(stabilities)),
        "mu": str(dataset.mu),
        "length_unit_km": str(dataset.length_unit_km),
        "time_unit_s": str(dataset.time_unit_s),
        "radius_secondary": str(dataset.radius_secondary),
        "script_status": dataset.script_status,
    }


def _orbit_record_to_csv_row(record: OrbitRecord) -> dict[str, str]:
    return {field: str(getattr(record, field)) for field in ORBIT_FIELDNAMES}


def _orbit_record_from_csv_row(row: dict[str, str]) -> OrbitRecord:
    return OrbitRecord(
        orbit_id=row["orbit_id"],
        dataset_id=row["dataset_id"],
        system=row["system"],
        source_orbit_type=row["source_orbit_type"],
        orbit_type=row["orbit_type"],
        variant=row["variant"],
        libration_point=row["libration_point"],
        branch=row["branch"],
        resonance=row["resonance"],
        source_file=row["source_file"],
        source_row=int(row["source_row"]),
        x=float(row["x"]),
        y=float(row["y"]),
        z=float(row["z"]),
        vx=float(row["vx"]),
        vy=float(row["vy"]),
        vz=float(row["vz"]),
        jacobi=float(row["jacobi"]),
        period=float(row["period"]),
        stability=float(row["stability"]),
        mu=float(row["mu"]),
        length_unit_km=float(row["length_unit_km"]),
        time_unit_s=float(row["time_unit_s"]),
        radius_secondary=float(row["radius_secondary"]),
        script_status=row["script_status"],
    )


def main(argv: list[str] | None = None) -> int:
    """命令行入口：生成 normalized CR3BP 数据 catalog。"""

    parser = argparse.ArgumentParser(description="导入 CR3BP 原始 XLSX 数据并生成 normalized catalog")
    parser.add_argument("--raw-dir", type=Path, required=True, help="原始 XLSX 数据目录")
    parser.add_argument("--output-dir", type=Path, required=True, help="normalized 输出目录")
    parser.add_argument("--overwrite", action="store_true", help="覆盖 importer 管理的输出文件")
    args = parser.parse_args(argv)

    try:
        report = import_cr3bp_xlsx_catalog(args.raw_dir, args.output_dir, overwrite=args.overwrite)
    except Cr3bpImportSchemaError as exc:
        print(f"Schema error: {exc}", file=sys.stderr)
        return 3
    except Cr3bpImportError as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Imported {report.datasets_imported} datasets and {report.orbits_imported} orbits "
        f"to {report.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
