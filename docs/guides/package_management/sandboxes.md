# Working in sandboxes

A notebook can carry its code and package requirements in the same file.
In sandbox mode, marimo prepares an **isolated environment** from the notebook's
requirements, independently of other notebooks or a surrounding project.

See the [package management overview](index.md) for when to use a sandbox or
[shared project requirements](projects.md).

## Open a notebook

marimo can prepare a notebook's sandbox with uv or Pixi. Choose your tool below
to open a notebook using its own requirements, without setting up a project.

=== "uv"

    With [uv installed](https://docs.astral.sh/uv/getting-started/installation/),
    you can use `uvx` to launch marimo and open your notebook:

    ```bash
    uvx marimo edit --sandbox notebook.py
    ```

    `uvx` installs and launches marimo, while `--sandbox` tells marimo to use
    uv to prepare a separate environment for the notebook's packages. uv is
    the default sandbox backend and installs Python packages from PyPI.

    If marimo is already installed, you can run
    `marimo edit --sandbox notebook.py` directly.

=== "Pixi"

    With [Pixi installed](https://pixi.prefix.dev/latest/installation/),
    you can use `pixi exec` to launch marimo and open your notebook:

    ```bash
    pixi exec marimo edit --sandbox=pixi notebook.py
    ```

    `pixi exec` installs and launches marimo, while
    `--sandbox=pixi` prepares the notebook's separate environment using Pixi,
    with support for both PyPI and Conda packages.

    If marimo is already installed, you can run
    `marimo edit --sandbox=pixi notebook.py` directly. Sandbox support requires
    Pixi 0.80.0 or later.

marimo starts the server that provides the editor separately from the notebook's
isolated environment. The editor can open while the notebook's packages are
being installed; the notebook's code runs once installation completes.

If installation fails, the editor remains available. You can inspect the error,
[edit the notebook's requirements and retry](#edit-metadata-and-sync-the-environment)
from the package panel, without restarting the marimo server.

The same sandbox option works with `marimo new` to create a notebook and
`marimo run` to serve it as an app.

The `--no-sandbox` option uses your current environment instead of the notebook's
requirements.

!!! note "Dependency isolation"

    Sandboxes isolate installed packages, not access to your files or network.
    Only run notebooks from sources you trust.

## Open a directory of notebooks

To work with several sandboxed notebooks, pass a directory instead of a file:

=== "uv"

    ```bash
    marimo edit --sandbox notebooks/
    ```

=== "Pixi"

    ```bash
    marimo edit --sandbox=pixi notebooks/
    ```

marimo opens the [home page](../editor_features/home.md#sandboxed-home) for the
directory. Each notebook gets its own environment, prepared from its requirements
when you open it. Package changes in one notebook do not affect the others.

## Manage notebook dependencies

### Inline script metadata { #auto-tracking-inline-script-metadata }

Python version and package requirements are recorded in a comment block at the
top of the notebook, using [inline script metadata (PEP 723)](https://peps.python.org/pep-0723/).

```python title="notebook.py (header)"
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
#     "altair",
# ]
# ///
```

The `requires-python` field specifies the Python version requirement, and
`dependencies` lists Python packages, typically from PyPI. marimo uses the
metadata to prepare the notebook's environment; uv and Pixi can also read it to
[run the notebook as a script](#run-and-share-the-notebook).

### Add and remove packages { #adding-and-removing-packages }

When you add or remove Python packages through the
[package panel](installing_packages.md), marimo updates both the notebook's
metadata and its environment, including when you accept a prompt to install
a missing package.

Removing an import alone does not remove its package requirement, since other
code may still need it.

You can also manage requirements from the terminal:

=== "uv"

    Use `uv add` or `uv remove` with `--script` to update the notebook's
    requirements rather than a project's:

    ```bash
    uv add --script notebook.py numpy
    uv remove --script notebook.py numpy
    ```

=== "Pixi"

    Use `pixi add` or `pixi remove` with `--script` to update the notebook's
    requirements. The `--pypi` flag selects Python packages from PyPI:

    ```bash
    pixi add --script notebook.py --pypi numpy
    pixi remove --script notebook.py --pypi numpy
    ```

<a id="edit-metadata-and-sync-the-environment"></a>

!!! tip "Edit metadata directly"

    For tool-specific settings or dependency problems, use **Edit manifest…** in
    the package panel to edit the notebook's metadata and sync its environment,
    even if sandbox setup has failed.

<a id="local-development-with-editable-installs"></a>

### Tool-specific configuration { #backend-specific-metadata }

Inline metadata can include settings specific to uv or Pixi. For example, a
sandbox needs an explicit dependency on a local library, since it doesn't
inherit project packages. An editable install lets the notebook use the
library's source without reinstalling after each change.

=== "uv"

    With `--sandbox=uv`, declare the local package in `tool.uv.sources`:

    ```python title="notebook.py (header)"
    # /// script
    # dependencies = ["marimo", "my-library"]
    #
    # [tool.uv.sources]
    # my-library = { path = "./my-library", editable = true }
    # ///
    ```

    See [uv's script guide](https://docs.astral.sh/uv/guides/scripts/) for more
    settings, including custom package indexes.

=== "Pixi"

    With `--sandbox=pixi`, declare the local package in `tool.pixi.pypi-dependencies`:

    ```python title="notebook.py (header)"
    # /// script
    # dependencies = ["marimo"]
    #
    # [tool.pixi.workspace]
    # channels = ["conda-forge"]
    #
    # [tool.pixi.pypi-dependencies]
    # my-library = { path = "./my-library", editable = true }
    # ///
    ```

    marimo does not apply Pixi activation scripts or activation environment variables.

The `./my-library` path is relative to the notebook. See
[module autoreloading](../editor_features/module_autoreloading.md) for how
marimo picks up source changes in an open notebook.

### Conda packages with Pixi { #pixi-sandboxes }

Pixi can manage non-Python dependencies, including system libraries and language
runtimes, alongside Python packages. For example, a notebook can include the R
runtime and [rpy2](https://rpy2.github.io/) from Conda to call R
from Python:

```python title="notebook.py (header)"
# /// script
# dependencies = ["marimo"]
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
#
# [tool.pixi.dependencies]
# r-base = "*"
# rpy2 = "*"
# ///
```

When you open the notebook with `marimo edit --sandbox=pixi notebook.py`,
Pixi installs marimo from PyPI and R and rpy2 from Conda. A Python cell
can then summarize R's built-in `iris` dataset:

```python
import rpy2.robjects as ro

print(ro.r("summary(iris)"))
```

For an interactive example combining a marimo slider, dplyr, Arrow, and Polars,
see the [Using R notebook](https://github.com/marimo-team/marimo/blob/main/examples/misc/using_r.py).

Manage [Conda dependencies](https://pixi.prefix.dev/latest/python/scripts/#manage-dependencies)
through the metadata or Pixi's script commands; marimo's package panel manages
PyPI dependencies.

### Using packages across platforms { #platform-specific-dependencies-pep-508 }

Some packages are needed only on certain platforms—for example, when running a
notebook locally versus in the browser with [WebAssembly](../wasm.md).
[Environment markers](https://peps.python.org/pep-0508/#environment-markers)
let you specify where each dependency should be installed.

For browser execution, Pyodide uses `"emscripten"` as its `sys.platform` value:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "torch; sys_platform != 'emscripten'",
#     "pyodide-http; sys_platform == 'emscripten'",
# ]
# ///
```

- `sys_platform != 'emscripten'` — install locally, skip in the browser.
- `sys_platform == 'emscripten'` — install only for WebAssembly / Pyodide.

Environment markers also apply when [exporting to WebAssembly
HTML](../exporting/webassembly_html.md). WebAssembly uses Pyodide's package set
and cannot install Conda dependencies.

## Run and share the notebook

The notebook file contains the requirements needed to prepare its environment.
If it doesn't depend on other local files, you can share it on its own, along
with the sandbox command you used to open it.

Any required data or local source files still need to be shared. Recipients with
uv or Pixi installed can open the notebook in marimo, or
[run it as a script](../scripts.md#running-with-inline-dependencies) using the
same inline requirements.

### Lock dependency versions

marimo updates the notebook's inline requirements as you manage packages in the
editor. Creating a **lockfile** is a separate step: use your package manager to
record exact versions, including dependencies of dependencies.

=== "uv"

    ```bash
    uv lock --script notebook.py
    ```

    uv writes `notebook.py.lock` alongside the notebook. See
    [uv's locking guide](https://docs.astral.sh/uv/guides/scripts/#locking-dependencies)
    for how subsequent commands use and update the lockfile.

=== "Pixi"

    ```bash
    pixi lock --script notebook.py
    ```

    Pixi writes `notebook.py.pixi.lock` alongside the notebook. See
    [Pixi's locking guide](https://pixi.prefix.dev/latest/python/scripts/#lock-exact-versions)
    for platform requirements and how subsequent commands use the lockfile.

Share the lockfile with the notebook so others can reuse the resolved versions.

### Sharing on the web { #sharing-on-the-web }

For a notebook hosted online, replace the file path in your sandbox command
with its URL. For example, you can open a notebook shared as a GitHub Gist:

=== "uv"

    ```bash
    uvx marimo edit --sandbox https://gist.github.com/kolibril13/a59135dd0973b97d488ba21c650667fe
    ```

=== "Pixi"

    ```bash
    pixi exec marimo edit --sandbox=pixi https://gist.github.com/kolibril13/a59135dd0973b97d488ba21c650667fe
    ```

Only run remote code you trust; a sandbox isolates packages, not access to your
files or network.

## Markdown notebooks { #specifying-dependencies-in-markdown-files }

marimo's sandbox mode also supports [Markdown notebooks](../editor_features/watching.md#as-markdown)
with either uv or Pixi:

=== "uv"

    ```bash
    uvx marimo edit --sandbox notebook.md
    ```

=== "Pixi"

    ```bash
    pixi exec marimo edit --sandbox=pixi notebook.md
    ```

Package requirements are stored as TOML under `pyproject` in the notebook's
frontmatter:

```markdown title="notebook.md (frontmatter)"
---
title: My Notebook
pyproject: |
  requires-python = ">=3.11"
  dependencies = ["marimo", "pandas", "altair"]
---
```
