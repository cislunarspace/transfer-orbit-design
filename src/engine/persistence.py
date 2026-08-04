r"""结果持久化 -- 将 DTO 写入 output/dro/ 目录。

双文件方案（ADR 对齐）：
- dro_<YYYYMMDDHHMMSS>.json -- 标量元数据
- dro_<YYYYMMDDHHMMSS>.npz  -- states + times（numpy 压缩）

文件命名与 discovery.py 的 ``_DRO_ORBIT_RE = r"^dro_\d+\.json$"`` 兼容。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.engine.facade_bridge import OrbitDesignResultData


def _timestamp() -> str:
    """生成 UTC 时间戳字符串 ``YYYYMMDDHHMMSS``。"""
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def save_artifact(
    result_data: OrbitDesignResultData,
    output_dir: Path,
) -> Path:
    """将计算结果写入 output/dro/ 目录，返回 JSON 文件路径。

    文件名格式 ``dro_<14位时间戳>``，与 discovery 正则兼容。
    """
    output_dir = Path(output_dir)
    dro_dir = output_dir / "dro"
    dro_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    stem = f"dro_{ts}"
    json_path = dro_dir / f"{stem}.json"
    npz_path = dro_dir / f"{stem}.npz"

    np.savez_compressed(npz_path, states=result_data.states, times=result_data.times)

    meta = {
        "orbit_type": result_data.orbit_type,
        "epoch_utc": result_data.epoch_utc,
        "duration_day": result_data.duration_day,
        "cr3bp_jacobi": result_data.cr3bp_jacobi,
        "correction_converged": result_data.correction_converged,
        "correction_iterations": result_data.correction_iterations,
        "initial_state": result_data.initial_state.tolist(),
        "states_shape": list(result_data.states.shape),
        "times_count": int(result_data.times.size),
        "arrays_file": npz_path.name,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return json_path
