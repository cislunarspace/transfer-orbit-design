"""Params for validate_geo_to_dro.py."""

from tod.gui.script_registry import ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "transfer",
    "validate_geo_to_dro",
    "验证 GEO→DRO 转移轨道搜索可行性",
    "tod/transfers/geo_to_dro/validate_geo_to_dro.py",
    output_dir="output/transfer",
    group_label="GEO→DRO",
)
