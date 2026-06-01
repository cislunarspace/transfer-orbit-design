from __future__ import annotations

from pathlib import Path

import pytest

from tod.generates.cr3bp._raw_naming import RawDatasetNameError, parse_raw_xlsx_name


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        (
            "earth-moon_dro.xlsx",
            {
                "dataset_id": "earth-moon_dro",
                "system": "earth-moon",
                "source_orbit_type": "dro",
                "orbit_type": "dro",
                "variant": "",
                "libration_point": "",
                "branch": "",
                "resonance": "",
            },
        ),
        (
            "earth-moon_halo_L1_N.xlsx",
            {
                "dataset_id": "earth-moon_halo_L1_N",
                "system": "earth-moon",
                "source_orbit_type": "halo",
                "orbit_type": "halo",
                "variant": "L1_N",
                "libration_point": "L1",
                "branch": "N",
                "resonance": "",
            },
        ),
        (
            "earth-moon_resonant_21.xlsx",
            {
                "dataset_id": "earth-moon_resonant_21",
                "system": "earth-moon",
                "source_orbit_type": "resonant",
                "orbit_type": "resonant",
                "variant": "21",
                "libration_point": "",
                "branch": "",
                "resonance": "21",
            },
        ),
        (
            "earth-moon_lpo_E.xlsx",
            {
                "dataset_id": "earth-moon_lpo_E",
                "system": "earth-moon",
                "source_orbit_type": "lpo",
                "orbit_type": "lpo_directional",
                "variant": "E",
                "libration_point": "",
                "branch": "E",
                "resonance": "",
            },
        ),
        (
            "earth-moon_short_L4.xlsx",
            {
                "dataset_id": "earth-moon_short_L4",
                "system": "earth-moon",
                "source_orbit_type": "short",
                "orbit_type": "spo",
                "variant": "L4",
                "libration_point": "L4",
                "branch": "",
                "resonance": "",
            },
        ),
        (
            "earth-moon_longp_L5.xlsx",
            {
                "dataset_id": "earth-moon_longp_L5",
                "system": "earth-moon",
                "source_orbit_type": "longp",
                "orbit_type": "lpo",
                "variant": "L5",
                "libration_point": "L5",
                "branch": "",
                "resonance": "",
            },
        ),
    ],
)
def test_parses_raw_cr3bp_dataset_names(filename: str, expected: dict[str, str]) -> None:
    parsed = parse_raw_xlsx_name(Path(filename))

    for field, value in expected.items():
        assert getattr(parsed, field) == value


def test_rejects_unparseable_raw_dataset_name() -> None:
    with pytest.raises(RawDatasetNameError, match="Cannot parse"):
        parse_raw_xlsx_name(Path("halo.xlsx"))


def test_rejects_non_xlsx_raw_dataset_name() -> None:
    with pytest.raises(RawDatasetNameError, match="extension"):
        parse_raw_xlsx_name(Path("earth-moon_halo_L1_N.csv"))
