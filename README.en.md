# transfer-orbit-design - Cislunar Orbit Design GUI

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

[中文](README.md) | English

transfer-orbit-design is the GUI frontend of [e2m2e](https://github.com/cislunarspace/e2m2e). e2m2e provides the dynamics models, correctors, continuators, and transfer algorithms required for cislunar orbit design; this repository wraps them into a visual desktop application. It implements no algorithms itself; it only does three things: calling (dispatching computations through the Facade API), managing (organizing every computation product as a Project/Artifact), and presenting (visualizing results on an embedded canvas). Users complete orbit design, station keeping, and result inspection through a three-step interaction of "select an artifact -> select an operation -> view the result".

## Installation

The project requires Python >= 3.13. Install with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

`uv sync` provisions the interpreter, creates the virtual environment, and installs all dependencies (including the core algorithm library `e2m2e>=5.6.7`) in one pass.

Windows users can also download the portable bundle `TransferOrbitDesign-windows.zip` from [GitHub Releases](https://github.com/cislunarspace/transfer-orbit-design/releases) and extract it; no configuration needed. Separately download `spice-kernels.zip` from the [`spice-data-v1`](https://github.com/cislunarspace/transfer-orbit-design/releases/tag/spice-data-v1) release and extract it next to `TransferOrbitDesign.exe` (producing a `kernels/` subdirectory); the application detects it at startup.

## SPICE Kernels

Ephemeris dynamics requires NASA SPICE kernel files. All required kernels are bundled in the `kernels-v1` release of [e2m2e](https://github.com/cislunarspace/e2m2e/releases). Three ways to configure:

- **Automatic download (recommended)**: `python scripts/download_kernels.py` idempotently fetches all kernels into `kernels/`.
- **Manual download**: download from the release above and extract into the `kernels/` directory.
- **Bring your own**: use your own kernel files, or point `$SPICE_KERNEL_DIR` at their location.

Official source: [NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html) (fallback).

## Quick Start

```bash
uv run transfer-orbit-design
```

The interface uses a three-column layout: project tree on the left, visualization canvas and log tabs in the center, tool selector, parameter panel, and run button on the right.

A walkthrough of orbit design:

1. Select "Orbit Design" in the tool selector on the right, choose an orbit type (DRO / Halo / NRHO, etc.) and fill in the parameters.
2. Click Run. Computation runs on a background thread while the log panel streams progress.
3. When finished, the result is persisted as a JSON + NPZ pair under `output/` and overlaid on the canvas.

The canvas toolbar switches between 3D / XY / XZ / YZ projections and toggles the Earth-Moon and L1-L5 annotations; Ctrl+click in the project tree selects multiple orbits for overlay comparison. Right-click an orbit in the project tree to launch station keeping and stability analysis.

## Capabilities

**Orbit design**

- Periodic orbit generation: DRO, NRHO, Halo, Lissajous, L4/L5; the parameter panel is auto-generated from Pydantic models, and results are persisted as JSON + NPZ pairs.

**Station keeping and analysis**

- Station keeping: Monte Carlo simulation with a selected orbit's ephemeris as input; outputs controlled ephemeris and delta-v statistics.
- Orbit family generation: continuation from a small-amplitude Halo seed to the target amplitude; a whole family is overlaid on the canvas.
- Stability analysis: Floquet multipliers / stability indices (nu1/nu2/nu3/Broucke) / bifurcation classification, shown in a dialog and persisted as JSON.

**Visualization**

- Multi-orbit visualization: 3D / XY / XZ / YZ projections, Earth-Moon and L1-L5 annotations, multi-orbit overlay.

For scripted workflows (CR3BP orbit generation, transfer search, ephemeris correction, plotting), use the [e2m2e CLI](https://github.com/cislunarspace/e2m2e); see the [Sphinx docs](https://cislunarspace.github.io/e2m2e/).

## Data Flow and Data Formats

The four tools follow the same data flow: fill in parameters in the panel (or right-click a selected orbit) -> the background thread calls e2m2e -> the result is written to `output/`. All products use the JSON + NPZ pair uniformly: JSON holds parameters and scalar statistics, NPZ holds orbit arrays. `<type>` is the lowercase orbit type (dro/halo/nrho/...), `<ts>` is a UTC timestamp.

| Tool | Input | Output |
|------|-------|--------|
| Orbit design | Orbit type, amplitude, phase, epoch, duration, step | `output/<type>/<type>_<ts>.json` + `.npz` |
| Station keeping | Ephemeris of the selected orbit + control parameters | `output/ephemeris/orbit_ephemeris_<ts>.json` + `.npz` |
| Family generation | Libration point, max out-of-plane amplitude, number of members | `output/family/family_<ts>.json` + `.npz` |
| Stability analysis | States and times of the selected orbit | `output/stability/<label>_stability_<ts>.json` |

Per-product JSON and NPZ contents:

- **Orbit design**: JSON holds orbit type, starting epoch, duration in days, mass ratio mu, Jacobi constant, convergence status and iteration count, initial state; NPZ holds `states` (n,6), `times` (n,), and ephemeris fields (UTC breakdown, GCRS position/velocity, synodic position, time).
- **Station keeping**: JSON holds failed-sample count, total delta-v, maneuver count; NPZ holds the controlled ephemeris `states` (n,6), `times` (n,), inertial position `position_km`, physical time `times_et`.
- **Family generation**: JSON holds libration point, member count, mass ratio; NPZ holds the family members `states` (m,n,6), `times` (m,n), out-of-plane amplitudes `z0s` (m,).
- **Stability analysis**: JSON only, holding the monodromy matrix, eigenvalues, stability indices (nu1/nu2/nu3/Broucke), bifurcation classification, and numerical errors.

## Documentation

Online docs: <https://cislunarspace.github.io/transfer-orbit-design/en/>

Local build:

```bash
uv sync --extra docs
uv run sphinx-build -b html -D language=en docs/source docs/build/html
```

## Tests and Code Standards

```bash
uv run pytest tests/ -m "not spice"
uv run ruff check .
uv run pyright
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[Apache 2.0](LICENSE)
