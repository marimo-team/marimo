# Package management

marimo supports package management for `pip, rye, uv, poetry, pixi`. When marimo comes across a module that is not installed, you will be prompted to install it using your preferred package manager.

Once the module is installed, all cells that depend on the module will be rerun.

```{admonition} Package Installation
:class: note

We use some heuristic for guessing the package name in your registry (e.g. PyPI) from the module name. It is possible that the package name is different from the module name. If you encounter an error, please file an issue, so we can correct the heuristic.
```

## Auto-add inline script metadata (`uv` only)

When using [uv](https://docs.astral.sh/uv), marimo can automatically add the package name metadata to your script, per [PEP 723](https://peps.python.org/pep-0723/). This metadata is used to manage the script's dependencies and Python version.

For example, if you start marimo in a new virtual environment and spin up a new notebook. Whenever you add a new module, marimo will automatically add the metadata to the script that will look like this:

```python
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "altair",
# ]
# ///
```
