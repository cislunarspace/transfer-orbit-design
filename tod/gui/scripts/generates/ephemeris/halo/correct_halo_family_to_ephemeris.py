from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

from tod.gui.scripts.generates.ephemeris._common import _ephemeris_conversion_cli_params

SCRIPT_ENTRY = ScriptEntry(
    "ephemeris",
    "correct_halo_family_to_ephemeris",
    "Halo 轨道族转换",
    "tod/generates/ephemeris/halo/correct_halo_family_to_ephemeris.py",
    output_dir="output/ephemeris",
    needs_spice=True,
    group_label="星历转换",
    cli_params=_ephemeris_conversion_cli_params("halo", "family"),
)
