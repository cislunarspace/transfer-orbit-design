"""转移链路验证：用 orbit_propagation / DRO 造目标星历，测 LGA/WSB/low_thrust。
Transfer-chain verification: build target ephemerides with orbit_propagation /
DRO and exercise LGA/WSB/low_thrust."""

import json
import os
import sys
import time

os.environ.setdefault("SPICE_KERNEL_DIR", "/dev/shm/kernels")


def run() -> None:
    from e2m2e.api import Facade

    f = Facade()
    res = {}

    # 1) 目标 A：月球环绕轨道（orbit_propagation，GCRS 月心 100km 圆轨道）
    # Target A: lunar orbit (orbit_propagation, GCRS Moon-centered 100 km circle).
    try:
        t0 = time.time()
        p = f.orbit_propagation(
            initial_state=[1837.0, 0.0, 0.0, 0.0, 1.633, 0.0],  # 月心 GCRS 近似
            epoch="2025-06-01T00:00:00",
            duration=6 * 86400.0,
            output_step=600.0,
        )
        import numpy as np

        states = np.column_stack([p.position_km, p.velocity_km_s])
        print("propagation:", p.n_points, "points", round(time.time() - t0, 1), "s")
        target_a = states
    except Exception as exc:  # noqa: BLE001
        print("propagation FAILED:", str(exc)[:200])
        target_a = None

    # 2) 目标 B：DRO 设计（稳定轨道）
    # Target B: DRO design (stable orbit).
    target_b = None
    try:
        t0 = time.time()
        d = f.design_orbit(orbit_type="DRO", epoch="2025-06-01T00:00:00")
        print("DRO design:", d.status, round(time.time() - t0, 1), "s")
        from dataclasses import fields as dc_fields

        from e2m2e.data.types import EphemerisTable

        import numpy as np

        if d.ephemeris:
            valid = {fl.name for fl in dc_fields(EphemerisTable)}
            target_b = EphemerisTable(
                **{k: np.asarray(v) for k, v in d.ephemeris.items()
                   if k in valid and v is not None}
            )
    except Exception as exc:  # noqa: BLE001
        print("DRO design FAILED:", str(exc)[:200])

    # 3) 转移测试矩阵
    # Transfer test matrix.
    for name, target in (("prop", target_a), ("dro", target_b)):
        if target is None:
            continue
        for ttype, extra in (
            ("HMN", {}),
            ("LGA", {}),
            ("WSB", {"tof_range": [10.0, 30.0]}),
        ):
            t0 = time.time()
            try:
                r = f.transfer_design(
                    transfer_type=ttype,
                    tli_epoch="2025-06-01T00:00:00",
                    target_ephemeris=target,
                    **extra,
                )
                n = len(r.trajectory) if r.trajectory else 0
                print(f"[{name}] {ttype}: {str(r.status).split('.')[-1]} "
                      f"dv={round(r.delta_v, 3)} n_traj={n} t={round(time.time()-t0, 1)}s")
                res[f"{name}_{ttype}"] = {
                    "status": str(r.status), "dv": r.delta_v, "n": n,
                    "detail_keys": list(r.details) if r.details else [],
                }
            except Exception as exc:  # noqa: BLE001
                print(f"[{name}] {ttype}: ERROR {str(exc)[:160]}")
                res[f"{name}_{ttype}"] = {"error": str(exc)[:300]}

    print("RESULTS:" + json.dumps(res))


if __name__ == "__main__":
    run()