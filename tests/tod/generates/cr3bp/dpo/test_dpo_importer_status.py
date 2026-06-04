from pathlib import Path

import pytest

from tod.generates.cr3bp._raw_naming import parse_raw_xlsx_name
from tod.generates.cr3bp.importer import script_status_for


def test_dpo_script_status_is_supported():
    name = parse_raw_xlsx_name(Path("earth-moon_dpo.xlsx"))
    assert script_status_for(name) == "supported"
