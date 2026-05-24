# Configuration file for the Sphinx documentation builder.

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Provide documentation-only shims for legacy e2m2e ephemeris APIs that some
# historical scripts still import. This keeps autodoc importable without
# changing runtime code paths.
class _DocStub:
    """Minimal object used only while Sphinx imports legacy modules."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return self

try:
    import types
    import e2m2e.core as _e2m2e_core

    for _name in ("SPICEManager", "EphemerisSystem", "EphemerisDynamics"):
        if not hasattr(_e2m2e_core, _name):
            setattr(_e2m2e_core, _name, _DocStub)

    _ephem_mod = types.ModuleType("e2m2e.algorithms.ephemeris_correction")
    _ephem_mod.EphemerisCorrectionResult = _DocStub
    _ephem_mod.correct_ephemeris_patch_points = lambda *args, **kwargs: _DocStub()
    sys.modules.setdefault("e2m2e.algorithms.ephemeris_correction", _ephem_mod)
except Exception:
    pass

project = "Transfer Orbit Design"
copyright = "2026, Authors"
author = "Authors"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = []
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = "_static/logo.png"
html_favicon = "_static/logo.png"

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "exclude-members": "clicked,doc_link_clicked,job_error,job_finished,job_output,job_started,stop_requested,status_message",
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
myst_heading_anchors = 3

suppress_warnings = ["myst.xref_missing"]
