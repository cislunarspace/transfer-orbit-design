"""Runner: execute Phase 2 pairs sequentially, logging to files."""

import subprocess, sys, time
from pathlib import Path

PYTHON = sys.executable
SCRIPT = str(Path(__file__).parent / "phase2_transfer_search.py")
OUTDIR = Path(__file__).resolve().parent.parent / "output"
OUTDIR.mkdir(exist_ok=True)

for idx in range(4):
    logf = OUTDIR / f"phase2_pair{idx}.log"
    print(f"[{time.strftime('%H:%M:%S')}] Starting pair {idx} ...  log -> {logf}")
    with open(logf, "w", encoding="utf-8") as log:
        proc = subprocess.run(
            [PYTHON, "-X", "utf8", "-u", SCRIPT, str(idx)],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).resolve().parent.parent),
            timeout=900,  # 15 min max per pair
        )
    print(f"[{time.strftime('%H:%M:%S')}] Pair {idx} done (rc={proc.returncode})")
    # show last 5 lines
    lines = logf.read_text(encoding="utf-8").splitlines()
    for ln in lines[-5:]:
        print(f"  | {ln}")

print("\nAll pairs processed.")
