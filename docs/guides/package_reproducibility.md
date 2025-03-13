# Package Reproducibility

marimo is the only Python notebook that is reproducible down to the packages,
serializing requirements in notebook files and running notebooks in
sandboxed venvs. This lets you share standalone notebooks without shipping
`requirements.txt` files alongside them, and guarantees your notebooks will
work weeks, months, even years into the future.

To opt-in to package reproducibility, use the `sandbox` flag:

=== "edit"

    ```bash
    marimo edit --sandbox notebook.py
    ```

=== "run"

    ```bash
    marimo run --sandbox notebook.py
    ```

=== "new"

    ```bash
    marimo new --sandbox
    ```

When running with `--sandbox`, marimo:

1. tracks the packages and versions used by your notebook, saving
   them in the notebook file;
2. runs in an isolated virtual environment ("sandbox") that only
   contains the notebook dependencies.

marimo's sandbox provides two key benefits. (1) Notebooks that carry their own
dependencies are easy to share — just send the `.py` file. (2) Isolating a
notebook from other installed packages prevents obscure bugs.

!!! note "Requires uv"

    Sandboxed notebooks require the uv package manager
    ([installation
    instructions](https://docs.astral.sh/uv/getting-started/installation/)).

!!! tip "Solving the notebook reproducibility crisis"

    marimo's support for package sandboxing is only possible because marimo
    notebooks are stored as pure Python files, letting marimo take advantage
    of new Python standards like [PEP
    723](https://peps.python.org/pep-0723/) and tools like uv. In contrast,
    traditional notebooks like Jupyter are stored as JSON files, and which suffer
    from a [reproducibility
    crisis](https://leomurta.github.io/papers/pimentel2019a.pdf) due to the lack
    of package management.

## Inline script metadata { #auto-tracking-inline-script-metadata }

When running with `--sandbox`, marimo automatically tracks package metadata in
your notebook file using inline script metadata, which per [PEP
723](https://peps.python.org/pep-0723/) is essentially a pyproject.toml inlined
as the script's header. This metadata is used to manage the
notebook's dependencies and Python version, and looks something like this:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas==<version>",
#     "altair==<version>",
# ]
# ///
```

!!! example "Example notebooks"

    The [example
    notebooks](https://github.com/marimo-team/marimo/tree/main/examples) in our
    GitHub repo were all created using `--sandbox`. Take a look at any of them
    for an example of the full script metadata.

### Adding and removing packages

When you import a module, if marimo detects that it is a third-party
package, it will automatically be added to the script metadata. Removing
an import does _not_ remove it from the script metadata (since library
code may still use the package).

Adding packages via the package manager panel will also add packages to script
metadata, and removing packages from the panel will in turn remove them from
the script metadata.

You can also edit the script metadata manually in an editor like VS Code or
neovim.

### Package locations

By default, marimo will look for packages on PyPI. You can edit the script
metadata to look for packages elsewhere, such as on GitHub. Consult the [Python
packaging
documentation](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#examples)
for more information.

### Local development with editable installs

When developing a local package, you can install it in editable mode using the `[tool.uv.sources]` section in the script metadata. For example:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "my-package",
# ]
#
# [tool.uv.sources]
# my-package = { path = "../", editable = true }
# ///
```

This is particularly useful when you want to test changes to your package without reinstalling it. The package will be installed in "editable" mode, meaning changes to the source code will be reflected immediately in your notebook.

## Configuration

Running marimo in a sandbox environment uses `uv` to create an isolated virtual
environment. You can use any of `uv`'s [supported environment
variables](https://docs.astral.sh/uv/configuration/environment/).

#### Choosing the Python version

For example, you can specify the Python version using the `UV_PYTHON` environment variable:

```bash
UV_PYTHON=3.13 marimo edit --sandbox notebook.py
```

#### Other common configuration

Another common configuration is `uv`'s link mode:

```bash
UV_LINK_MODE="copy" marimo edit --sandbox notebook.py
```
