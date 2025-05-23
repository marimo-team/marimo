# Package management

marimo supports package management for `pip`, `uv`, `poetry`, `pixi`, and
`rye`. When marimo comes across a module that is not installed, you will be
prompted to install it using your preferred package manager.

Once the module is installed, all cells that depend on the module will be rerun.

!!! note "Package Installation"

    We use some heuristic for guessing the package name in your registry (e.g. PyPI) from the module name. It is possible that the package name is different from the module name. If you encounter an error, please file an issue or help us by adding your mapping [directly to the codebase](https://github.com/marimo-team/marimo/blob/main/marimo/_runtime/packages/module_name_to_pypi_name.py).

## Package reproducibility

marimo is the only Python notebook that is reproducible down to the packages
they use. This makes it possible to share standalone notebooks without shipping
`requirements.txt` files alongside them, and guarantees your notebooks will
work weeks, months, even years into the future.

To learn more, see the [package reproducibility guide](../package_management/inlining_dependencies.md).
