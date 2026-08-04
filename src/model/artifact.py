from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from numpy import ndarray


@dataclass
class Artifact:
    """Represents a computed orbital artifact (orbit, family, transfer, ephemeris)."""

    artifact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    artifact_type: str = ""  # "orbit" | "family" | "transfer" | "ephemeris"
    label: str = ""
    orbit_type: str = ""  # DRO / Halo / NRHO / ...
    source_tool: str = ""
    state_data: ndarray | None = None  # (n, 6) state matrix
    times: ndarray | None = None  # (n,) time vector
    output_path: Path | None = None
    extra: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_summary(self) -> dict:
        """Return a summary dict excluding large array fields (state_data, times)."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "label": self.label,
            "orbit_type": self.orbit_type,
            "source_tool": self.source_tool,
            "output_path": str(self.output_path) if self.output_path else None,
            "extra": self.extra,
            "created_at": self.created_at.isoformat(),
        }
