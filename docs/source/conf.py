# Configuration file for the Sphinx documentation builder.

project = 'Transfer Orbit Design'
copyright = '2026, Authors'
author = 'Authors'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
exclude_patterns = []

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Logo
html_logo = '_static/logo.png'
html_favicon = '_static/logo.png'

# autodoc settings
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
}
