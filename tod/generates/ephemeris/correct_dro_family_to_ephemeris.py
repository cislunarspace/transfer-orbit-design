"""correct_dro_family_to_ephemeris — 向后兼容包装。

实际逻辑已移至 tod.generates.ephemeris.family_correction。
"""

from tod.generates.ephemeris.family_correction import SCRIPT_ENTRIES

SCRIPT_ENTRY = SCRIPT_ENTRIES[0]


def main(argv=None):
    from tod.generates.ephemeris import _conversion
    return _conversion.main_family("dro", argv)
