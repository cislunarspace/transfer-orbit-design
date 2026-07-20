"""解析 CR3BP 原始 XLSX 数据文件名。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

class RawDatasetNameError(ValueError):
    """原始数据文件名无法解析。"""

@dataclass(frozen=True)
class RawDatasetName:
    """从原始 XLSX 文件名解析出的数据集身份。"""

    dataset_id: str
    system: str
    source_orbit_type: str
    orbit_type: str
    variant: str
    libration_point: str
    branch: str
    resonance: str
    source_file: str

SOURCE_ORBIT_TYPE_MAP = {
    "short": "spo",
    "longp": "lpo",
    "lpo": "lpo_directional",
}

def parse_raw_xlsx_name(path: Path) -> RawDatasetName:
    """解析形如 ``earth-moon_halo_L1_N.xlsx`` 的原始数据文件名。"""

    if path.suffix.lower() != ".xlsx":
        raise RawDatasetNameError(f"Unsupported raw dataset extension: {path.name}")

    stem = path.stem
    parts = stem.split("_")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise RawDatasetNameError(f"Cannot parse CR3BP raw dataset filename: {path.name}")

    system = parts[0]
    source_orbit_type = parts[1]
    variant_parts = parts[2:]
    variant = "_".join(variant_parts)
    orbit_type = SOURCE_ORBIT_TYPE_MAP.get(source_orbit_type, source_orbit_type)

    libration_point = ""
    branch = ""
    resonance = ""

    for token in variant_parts:
        if token in {"L1", "L2", "L3", "L4", "L5"}:
            libration_point = token
        elif token in {"N", "S", "E", "W"}:
            branch = token
        elif source_orbit_type == "resonant" and token.isdigit():
            resonance = token
        elif source_orbit_type == "resonant":
            raise RawDatasetNameError(f"Invalid resonant suffix in raw dataset filename: {path.name}")

    return RawDatasetName(
        dataset_id=stem,
        system=system,
        source_orbit_type=source_orbit_type,
        orbit_type=orbit_type,
        variant=variant,
        libration_point=libration_point,
        branch=branch,
        resonance=resonance,
        source_file=path.name,
    )
