# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import datetime
import os
import sys

# If modules to document with autodoc (or sphinx extensions) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it absolute,
# like shown here.
#
# To import marimo:
sys.path.insert(0, os.path.abspath(".."))
# To import helpers
sys.path.insert(0, os.path.abspath("."))

from helpers.md2rst import md2rst
from helpers.sections import PublicMethods
from helpers.copy_readme import ReadmePartDirective

import marimo

project = "marimo"
copyright = f"{datetime.datetime.now().year}, marimo-team"
author = "marimo-team"
release = marimo.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    # Write source in markdown, not rst
    "myst_parser",
    # For API docs
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx_copybutton",
    "sphinx_new_tab_link",
    "sphinx_sitemap",
    # To generate tables of inherited members
    "autoclasstoc",
]


autoclasstoc_sections = [
    PublicMethods.key,
    "public-attrs",
]

# Group symbols by the order they appear in source
autodoc_member_order = "bysource"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_favicon = "_static/favicon-32x32.png"
html_baseurl = "https://docs.marimo.io/"
html_css_files = [
    # Font Awesome
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/fontawesome.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/solid.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/brands.min.css",
    # Inter font
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=block",
    # Fira Mono font
    "https://fonts.googleapis.com/css2?family=Fira+Mono&display=block",
    "css/custom.css",
]
html_js_files = [
    "js/analytics.js",
]
html_title = f"{project}"
html_theme_options = {
    "sidebar_hide_name": True,
    "light_logo": "marimo-logotype-thick.svg",
    "dark_logo": "marimo-logotype-thick.svg",
    # Show edit on github button
    "source_repository": "https://github.com/marimo-team/marimo",
    "source_branch": "main",
    "source_directory": "docs/",
    "light_css_variables": {
        "color-brand-primary": "#1C7362",
        "color-brand-content": "#1C7362",
    },
    "light_css_variables": {
        "font-stack": "Inter, sans-serif",
        "font-stack--monospace": "Fira Mono",
        "code-font-size": "0.875rem",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/marimo-team/marimo",
            "html": "",
            "class": "fa-brands fa-solid fa-github fa-2x",
        },
        {
            "name": "Discord",
            "url": "https://discord.gg/JE7nhX6mD8",
            "html": "",
            "class": "fa-brands fa-solid fa-discord fa-2x",
        }
    ],
}

pygments_style = "monokai"
pygments_dark_style = "monokai"


# -- Hooks -------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/extdev/appapi.html#events
def setup(app):
    # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#docstring-preprocessing
    app.connect("autodoc-process-docstring", md2rst)
    app.add_directive('readmepart', ReadmePartDirective)
