"""服务器上扫描 NRHO 设计参数 + LGA/WSB 转移链路验证。

用法（在服务器上）：
    .venv/bin/python scan_transfer.py [n_workers]
输出 JSON 到 stdout 末行（RESULTS: 前缀）。
"""

import json
import multiprocessing as mp
import os
import sys
import time

KDIR = "/dev/shm/kernels"
os.environ["SPICE_KERNEL_DIR"] = KDIR


def _try_design(args):
    amp, epoch, nsp = args
    from e2m2e.api import Facade

    f = Facade()
    t0 = time.time()
    try:
        d = f.design_orbit(
            orbit_type="NRHO",
            collinear_point=2,
            north_south=nsp,
            amplitude=amp,
            epoch=epoch,
        )
        eph = getattr(d, "ephemeris", None) or (d.details or {}).get("ephemeris")
        return (amp, epoch, nsp, True, time.time() - t0, type(eph).__name__)
    except Exception as exc:  # noqa: BLE001
        return (amp, epoch, nsp, False, time.time() - t0, str(exc)[:120])


def _try_transfer(job):
    ttype, amp, epoch = job
    from e2m2e.api import Facade

    f = Facade()
    try:
        d = f.design_orbit(
            orbit_type="NRHO", collinear_point=2, amplitude=amp, epoch=epoch
        )
        eph = getattr(d, "ephemeris", None) or (d.details or {}).get("ephemeris")
        kw = dict(
            transfer_type=ttype,
            tli_epoch=epoch,
            target_ephemeris=eph,
        )
        if ttype == "WSB":
            kw["tof_range"] = [10.0, 30.0]
        r = f.transfer_design(**kw)
        return (ttype, amp, epoch, str(r.status), round(r.delta_v, 3), None)
    except Exception as exc:  # noqa: BLE001
        return (ttype, amp, epoch, "ERROR", None, str(exc)[:160])


def main() -> None:
    n_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    amps = [800.0, 1200.0, 1500.0, 2000.0, 3000.0, 5000.0, 8000.0]
    epochs = ["2025-06-01T00:00:00", "2025-03-20T00:00:00", "2025-11-05T00:00:00"]
    jobs = [(a, e, n) for a in amps for e in epochs for n in (1, 2)]
    with mp.Pool(n_workers) as pool:
        design_res = pool.map(_try_design, jobs)

    ok = [(r[0], r[1]) for r in design_res if r[3]]
    print("== NRHO 设计扫描 ==")
    for r in design_res:
        print(f"amp={r[0]:7.0f} epoch={r[1]} ns={r[2]} ok={r[3]} t={r[4]:.1f}s {r[5]}")
    print(f"收敛 {len(ok)}/{len(jobs)}")

    trans_res = []
    if ok:
        tjobs = [(t, a, e) for (a, e) in ok[:4] for t in ("LGA", "WSB")]
        with mp.Pool(min(n_workers, len(tjobs))) as pool:
            trans_res = pool.map(_try_transfer, tjobs)
        print("== 转移链路 ==")
        for r in trans_res:
            print(f"type={r[0]} amp={r[1]} epoch={r[2]} status={r[3]} dv={r[4]} {r[5] or ''}")

    print("RESULTS:" + json.dumps({"design": design_res, "transfer": trans_res}))


if __name__ == "__main__":
    main()