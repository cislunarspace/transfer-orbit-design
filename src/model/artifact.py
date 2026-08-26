from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from numpy import ndarray


@dataclass
class Artifact:
    """Represents a computed orbital artifact (orbit, family, transfer, ephemeris).

    ``state_data`` / ``times`` 允许构造后原地填充（catalog 记录懒加载，
    见 ``engine.catalog_service.load_arrays``）；需要快照的调用方请先
    ``copy.deepcopy``。
    """

    artifact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    artifact_type: str = ""  # "orbit" | "family" | "transfer" | "ephemeris"
    label: str = ""
    orbit_type: str = ""  # DRO / Halo / NRHO / ...
    source_tool: str = ""
    # 轨道库记录 id（e2m2e catalog，issue #375）：catalog 产物的主键，
    # 此时 artifact_id 与之相同；非 catalog 产物（transfer 遗留分区）为 None。
    record_id: str | None = None
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
            "record_id": self.record_id,
            "output_path": str(self.output_path) if self.output_path else None,
            "extra": self.extra,
            "created_at": self.created_at.isoformat(),
        }
