# Package management

marimo supports package management for `pip, rye, uv, poetry, pixi`. When marimo comes across a module that is not installed, you will be prompted to install it using your preferred package manager.

Once the module is installed, all cells that depend on the module will be rerun.

```{admonition} Package Installation
:class: note

We use some heuristic for guessing the package name in your registry (e.g. PyPI) from the module name. It is possible that the package name is different from the module name. If you encounter an error, please file an issue or help us by adding your mapping [directly to the codebase](https://github.com/marimo-team/marimo/blob/main/marimo/_runtime/packages/module_name_to_pypi_name.py).
```

## Auto-add inline script metadata (`uv` only)

When using [uv](https://docs.astral.sh/uv), marimo can automatically update the package name metadata in your notebook file, per [PEP 723](https://peps.python.org/pep-0723/). This metadata is used to manage the notebook's dependencies and Python version.

For example, say you start marimo in a new virtual environment and spin up a new notebook. Whenever you add a new package, marimo will automatically add script metadata that looks like this:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "altair",
# ]
# ///
```

## Running `marimo` in a sandbox environment (`uv` only)

If you want to run marimo in a sandbox environment, you can use the `--sandbox` flag. This will create a new virtual environment (using [uv](https://docs.astral.sh/uv)) and install any packages listed in the script metadata, per [PEP 723](https://peps.python.org/pep-0723/).
This is useful when you want to run marimo in a clean environment without affecting your global environment.

```bash
marimo edit --sandbox notebook.py
```

If there is not package metadata in the script, marimo will still prompt you to install any missing packages.
