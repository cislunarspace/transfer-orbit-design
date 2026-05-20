from __future__ import annotations

from e2m2e.algorithms.ephemeris_correction import (
    EphemerisCorrectionResult,
    correct_ephemeris_patch_points as _e2m2e_correct_ephemeris_patch_points,
)


def correct_ephemeris_patch_points(*args, **kwargs) -> EphemerisCorrectionResult:
    return _e2m2e_correct_ephemeris_patch_points(*args, **kwargs)
