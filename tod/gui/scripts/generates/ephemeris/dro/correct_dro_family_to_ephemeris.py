from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

from tod.gui.scripts.generates.ephemeris._common import _ephemeris_conversion_cli_params

SCRIPT_ENTRY = ScriptEntry(
    "ephemeris",
    "correct_dro_family_to_ephemeris",
    "DRO 轨道族转换",
    "tod/generates/ephemeris/dro/correct_dro_family_to_ephemeris.py",
    output_dir="output/ephemeris",
    needs_spice=True,
    group_label="星历转换",
    cli_params=_ephemeris_conversion_cli_params("dro", "family"),
)
