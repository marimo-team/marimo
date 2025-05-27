# Installing packages

marimo supports package management for `pip`, `uv`, `poetry`, `pixi`, and
`rye`. When marimo comes across a module that is not installed, you will be
prompted to install it using your preferred package manager. Once the module is
installed, all cells that depend on the module will be rerun
(or marked as stale).

You can also install (and remove) packages using the package manager sidebar panel.

!!! note "Resolving package names"

    We use a heuristic for guessing the package name in your registry (e.g. PyPI) from the module name. It is possible that the package name is different from the module name. If you encounter an error, please [file an issue](https://github.com/marimo-team/marimo/issues) or help us by adding your mapping [directly to the codebase](https://github.com/marimo-team/marimo/blob/main/marimo/_runtime/packages/module_name_to_pypi_name.py).

**Notes.**

* When using imperative style package managers like `pip`, packages are installed directly
in the active virtual environment.
* When using `uv`, marimo will decide whether to add it to your `pyproject.toml`
(if running as part of a uv project), or whether to install it imperatively with `uv pip` (otherwise).
* When running in a [package sandbox](inlining_dependencies.md), package installation
and removal also updates the notebook's inline dependencies.
