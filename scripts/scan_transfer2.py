"""服务器上扫描 NRHO（perilune_height）设计 + LGA/WSB 转移链路验证。

用法（在服务器上）：
    .venv/bin/python scripts/scan_transfer2.py [n_workers]
"""

import json
import multiprocessing as mp
import os
import sys
import time

KDIR = "/dev/shm/kernels"
os.environ["SPICE_KERNEL_DIR"] = KDIR


def _get_eph(response):
    """从 DesignOrbitResponse 取星历并重建 EphemerisTable（transfer_orbit 支持的类型）。"""
    from dataclasses import fields as dc_fields

    import numpy as np
    from e2m2e.data.types import EphemerisTable

    mapping = response.ephemeris
    if not mapping:
        return None
    valid = {f.name for f in dc_fields(EphemerisTable)}
    return EphemerisTable(
        **{k: np.asarray(v) for k, v in mapping.items() if k in valid and v is not None}
    )


def _design(f, perilune, epoch, ns):
    kw = dict(
        orbit_type="NRHO",
        collinear_point=2,
        perilune_height=perilune,
        epoch=epoch,
    )
    if ns is not None:
        kw["north_south"] = ns
    return f.design_orbit(**kw)


def _try_design(args):
    perilune, epoch, ns = args
    from e2m2e.api import Facade

    f = Facade()
    t0 = time.time()
    try:
        d = _design(f, perilune, epoch, ns)
        eph = _get_eph(d)
        return (perilune, epoch, ns, True, round(time.time() - t0, 1), eph is not None)
    except Exception as exc:  # noqa: BLE001
        return (perilune, epoch, ns, False, round(time.time() - t0, 1), str(exc)[:120])


def _try_transfer(job):
    ttype, perilune, epoch = job
    from e2m2e.api import Facade

    f = Facade()
    t0 = time.time()
    try:
        eph = _get_eph(_design(f, perilune, epoch, None))
        kw = dict(transfer_type=ttype, tli_epoch=epoch, target_ephemeris=eph)
        if ttype == "WSB":
            kw["tof_range"] = [10.0, 30.0]
        r = f.transfer_design(**kw)
        n = len(r.trajectory) if r.trajectory else 0
        return (ttype, perilune, epoch, str(r.status).split(".")[-1],
                round(r.delta_v, 3), n, round(time.time() - t0, 1))
    except Exception as exc:  # noqa: BLE001
        return (ttype, perilune, epoch, "ERROR", None, None, str(exc)[:160])


def main() -> None:
    n_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    perils = [100.0, 500.0, 1000.0, 2000.0, 3000.0, 5000.0]
    epochs = ["2025-06-01T00:00:00", "2024-03-20T00:00:00", "2025-01-15T00:00:00"]
    jobs = [(p, e, n) for p in perils for e in epochs for n in (1, None)]
    with mp.Pool(n_workers) as pool:
        design_res = pool.map(_try_design, jobs)

    print("== NRHO 设计扫描（perilune_height）==")
    ok = []
    for r in design_res:
        print(f"perilune={r[0]:6.0f} epoch={r[1]} ns={r[2]} ok={r[3]} t={r[4]}s {r[5]}")
        if r[3]:
            ok.append((r[0], r[1]))
    print(f"收敛 {len(ok)}/{len(jobs)}")

    trans_res = []
    if ok:
        tjobs = [(t, p, e) for (p, e) in ok[:6] for t in ("LGA", "WSB")]
        with mp.Pool(min(n_workers, len(tjobs))) as pool:
            trans_res = pool.map(_try_transfer, tjobs)
        print("== 转移链路 ==")
        for r in trans_res:
            print(f"type={r[0]} perilune={r[1]} epoch={r[2]} status={r[3]} "
                  f"dv={r[4]} n_traj={r[5]} t={r[6]}s")

    print("RESULTS:" + json.dumps({"design": design_res, "transfer": trans_res}))


if __name__ == "__main__":
    main()