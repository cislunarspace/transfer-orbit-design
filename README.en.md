# transfer-orbit-design — Cislunar Orbit Design GUI and Script Toolkit

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/cislunarspace/transfer-orbit-design?style=flat)](https://github.com/cislunarspace/transfer-orbit-design/stargazers)
[![Issues](https://img.shields.io/github/issues/cislunarspace/transfer-orbit-design)](https://github.com/cislunarspace/transfer-orbit-design/issues)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

[中文](README.md) | English

transfer-orbit-design is the **GUI frontend and script toolkit** of e2m2e. e2m2e provides the dynamics models, correctors, continuators, and transfer algorithms required for cislunar orbit design; this repository wraps them into a visual desktop application and reproducible scripts. It implements no algorithms itself — it does three things: calling (dispatching computations through the e2m2e Facade API), managing (organizing every computation artifact as a Project/Artifact), and presenting (visualizing results on an embedded canvas). Users never touch algorithm internals: a three-step interaction — select an artifact, select an operation, view the result — covers orbit design, station-keeping, and result inspection.

## Installation

### Clone the e2m2e dependency

The core algorithms depend on `e2m2e`, configured in `pyproject.toml` as a local path dependency (`../e2m2e`). `uv sync` will not fetch it from a remote, so clone it into the directory next to this repository first:

```bash
cd ..
git clone https://github.com/cislunarspace/e2m2e.git
cd transfer-orbit-design
```

There is no need to install anything inside e2m2e; the `uv sync` step below installs it in editable mode.

### uv (recommended)

The project requires Python `>=3.13`, pinned via `.python-version`. From the repository root:

```bash
uv sync
```

`uv sync` does it all in one pass: provisions the Python 3.13 interpreter, creates the virtual environment, installs all PyPI dependencies, and installs both `../e2m2e` and this project in editable mode. If the two repositories are not siblings, adjust the `tool.uv.sources.e2m2e` path in `pyproject.toml` first.

### Packaged build (Windows portable bundle + SPICE kernels)

Download `TransferOrbitDesign-windows.zip` from GitHub Releases and extract it — no environment variables needed. Also download `spice-kernels.zip` from the [`spice-data-v1`](https://github.com/cislunarspace/transfer-orbit-design/releases/tag/spice-data-v1) release and extract it next to `TransferOrbitDesign.exe` (producing a `kernels/` subdirectory); the application detects it at startup. An explicitly set `SPICE_KERNEL_DIR` environment variable still takes precedence. That release also ships the MICE toolkit (for full development with MATLAB and similar tools); it is not required to run this application.

### SPICE kernels

Ephemeris dynamics requires NASA SPICE kernel files, placed in `kernels/` or the path pointed to by `$SPICE_KERNEL_DIR`. The nine required kernels are `de430.bsp`, `de440s.bsp`, `earth_latest_high_prec.bpc`, `SPICEEarthPredictedKernel.bpc`, `SPICELunaCurrentKernel.bpc`, `SPICELunaFrameKernel.tf`, `naif0011.tls`, `naif0012.tls`, and `pck00010.tpc`. The recommended source is the `kernels-v1` bundle from [e2m2e Releases](https://github.com/cislunarspace/e2m2e/releases) (accessible from within China); [NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html) is the fallback.

## Quick Start

### GUI

```bash
uv run transfer-orbit-design
```

On startup the GUI scans the `output/` directory and rebuilds historical results into project-tree artifacts. The interface uses a three-column layout: project tree on the left, visualization canvas + log tabs in the center, and tool selector + parameter panel + run button on the right.

A complete orbit-design walkthrough:

1. Select the "Orbit Design" tool on the right.
2. Set the orbit type to DRO, then fill in the amplitude (km), phase (0–1), starting epoch, duration, and output step.
3. Click Run. Computation runs on a background thread while the log panel streams progress.
4. When finished, the result is persisted as an `output/dro/dro_<ts>.json` + `.npz` pair and overlaid on the canvas.
5. The toolbar switches between 3D / XY / XZ / YZ projections and toggles the Earth-Moon and L1–L5 annotations; Ctrl+click in the project tree selects multiple orbits for overlay comparison.

Station keeping: right-click an orbit in the project tree → select "Station Keeping" → Monte Carlo simulation runs with that orbit's ephemeris as input, and the results are written to `output/ephemeris/`.

### Scripts and CLI

For the script workflows — CR3BP orbit generation, transfer search and optimization, ephemeris correction, plotting — use the [e2m2e CLI](https://github.com/cislunarspace/e2m2e); see the [Sphinx docs](https://cislunarspace.github.io/e2m2e/).

## Mission and Progress

Cislunar orbit design demands algorithms that are accurate and tools that are usable. e2m2e builds the algorithm-toolkit infrastructure for the cislunar direction — dynamics modeling, orbit family generation, transfer design; transfer-orbit-design brings those capabilities to the human-computer interaction layer: a visual desktop application, parameter management, and result persistence and inspection. In short, e2m2e computes, this repository presents. The overall architecture is documented in [docs/architecture/architecture.md](docs/architecture/architecture.md), with individual decisions in [docs/adr/](docs/adr/).

| Capability | Status | Notes |
|------|---------|------|
| Orbit design (DRO/NRHO/Halo/Lissajous/L4/L5) | Implemented | Parameter panel auto-generated from Pydantic models; results persisted as JSON+NPZ pairs |
| Station keeping (Monte Carlo) | Implemented | Takes a selected orbit's ephemeris as input; outputs controlled ephemeris and Δv statistics |
| Multi-orbit visualization | Implemented | 3D/XY/XZ/YZ projections, Earth-Moon/L1–L5 annotations, multi-orbit overlay |
| Artifact persistence loop | Implemented | Scans `output/` on startup to rebuild the Project; lazy NPZ loading |
| CLI script workflow | Implemented (legacy) | Via e2m2e CLI; see e2m2e docs |
| Orbit family generation / stability analysis | Planned | Greyed-out placeholder in the tool selector |

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
