from __future__ import annotations

from pathlib import Path


def test_dro_catalog_seed_gui_adr_records_v1_contract() -> None:
    adr = Path("docs/adr/0002-dro-catalog-seed-gui-v1.md")

    text = adr.read_text(encoding="utf-8")

    required_terms = [
        "DRO single-orbit Generate",
        "Seed ID",
        "Jacobi nearest-neighbor",
        "manual/catalog mutual exclusion",
        "lazy normalized catalog",
        "SCRIPT_ENTRY",
        "period multiplier",
        "num points",
        "DOP853",
        "rtol=atol=1e-12",
        "Cr3bpCatalogSeedSelector",
        "ordinary CLI args",
    ]
    for term in required_terms:
        assert term in text
