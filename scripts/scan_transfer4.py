"""LGA/WSB 正确契约验证：synodic 物理单位目标态（对齐 e2m2e test_lga）。"""

import json
import math
import os
import time

import numpy as np

os.environ.setdefault("SPICE_KERNEL_DIR", "/dev/shm/kernels")


def main() -> None:
    from e2m2e.algorithm.transfer import LgaSearchParams, TliParams, transfer_orbit
    from e2m2e.api import Facade

    from e2m2e.algorithm.dynamics import CR3BP_Dynamics, CR3BP_System

    MU = 1.21506683e-2
    system = CR3BP_System(mu=MU, primary="Earth", secondary="Moon")._with_default_scales()
    du = system.characteristic_length
    vu = system.characteristic_velocity

    def synodic_target(r_km):
        x = (1.0 - MU) + r_km / du
        v = math.sqrt(MU / (r_km / du))
        return np.array([x * du, 0.0, 0.0, 0.0, v * vu, 0.0]).reshape(1, 6)

    res = {}
    for r_km in (2000.0, 5000.0, 10000.0, 1837.0 + 100.0):
        t0 = time.time()
        try:
            r = transfer_orbit(
                "LGA",
                tli_params=TliParams(parking_alt_km=200.0, inclination_deg=28.5),
                target_ephemeris=synodic_target(r_km),
                lga_search_params=LgaSearchParams(
                    n_departure_phase=360, n_tof=5,
                    max_total_dv=25.0, perilune_alt_min=100.0, perilune_alt_max=10000.0,
                ),
            )
            n = len(r.trajectory) if r.trajectory is not None else 0
            print(f"LGA r={r_km:.0f}km: {str(r.status).split('.')[-1]} dv={r.delta_v:.3f} "
                  f"n={n} t={time.time()-t0:.1f}s")
            res[f"lga_{int(r_km)}"] = {"status": str(r.status), "dv": r.delta_v, "n": n}
        except Exception as exc:  # noqa: BLE001
            print(f"LGA r={r_km:.0f}km: ERROR {exc}")
            res[f"lga_{int(r_km)}"] = {"error": str(exc)[:200]}

    # WSB 同契约
    for r_km in (2000.0, 5000.0):
        t0 = time.time()
        try:
            r = transfer_orbit(
                "WSB",
                tli_params=TliParams(parking_alt_km=200.0, inclination_deg=28.5),
                target_ephemeris=synodic_target(r_km),
                tof_range=(10.0, 30.0),
            )
            n = len(r.trajectory) if r.trajectory is not None else 0
            print(f"WSB r={r_km:.0f}km: {str(r.status).split('.')[-1]} dv={r.delta_v:.3f} "
                  f"n={n} t={time.time()-t0:.1f}s")
            res[f"wsb_{int(r_km)}"] = {"status": str(r.status), "dv": r.delta_v, "n": n}
        except Exception as exc:  # noqa: BLE001
            print(f"WSB r={r_km:.0f}km: ERROR {exc}")
            res[f"wsb_{int(r_km)}"] = {"error": str(exc)[:200]}

    # facade 层透传验证（TransferDesignRequest 路径）
    try:
        f = Facade()
        fr = f.transfer_design(
            transfer_type="LGA",
            tli_epoch="2025-06-01T00:00:00",
            parking_alt_km=200.0,
            incl_deg=28.5,
            target_ephemeris=synodic_target(2000.0),
        )
        print("facade LGA:", str(fr.status).split(".")[-1], round(fr.delta_v, 3))
        res["facade_lga"] = {"status": str(fr.status), "dv": fr.delta_v}
    except Exception as exc:  # noqa: BLE001
        print("facade LGA ERROR:", str(exc)[:200])
        res["facade_lga"] = {"error": str(exc)[:300]}

    print("RESULTS:" + json.dumps(res))


if __name__ == "__main__":
    main()
