# Package management

Notebooks often use Python packages, such as `matplotlib` or `polars`, that
must be installed before their code can run. **Package managers** handle
installing these libraries and their dependencies. marimo integrates with these
tools so you can [manage packages from the editor](installing_packages.md).

## Choosing a workflow

A notebook's **requirements** record which packages it needs and any
constraints on their versions. You can share requirements across a project or
store them inside individual notebooks.

A [project](projects.md) lets several notebooks and scripts _share_
requirements. A single configuration file (e.g., `pyproject.toml`) defines a
shared environment, so package changes apply to all notebooks within a project.

In [sandbox mode](sandboxes.md), each notebook carries its _own_ requirements
inside its file. marimo prepares a separate environment for each notebook from
those requirements and records package changes back into the notebook's file.

Both approaches can coexist in one repository. As a rule of thumb,
project-level requirements work well when you want to share the **project**
(e.g., a whole repository that others will clone), while notebook-level
requirements work well when you want to share the **notebook** (e.g., a
standalone file shared as a Gist).

## Choosing a package manager

For either workflow, a package manager prepares the environment where your
notebook runs. marimo supports [several package
managers](installing_packages.md) for projects. Notebook sandboxes require
**uv** or **Pixi**, two popular package managers that also work with projects:

- **[uv](https://docs.astral.sh/uv/)** is a Python package and project manager.
  It manages Python, environments, and packages from PyPI (the Python Package
  Index) in one tool.
- **[Pixi](https://pixi.prefix.dev/)** manages environments across languages using
  Conda and PyPI packages. Choose it if you're coming from the Conda ecosystem,
  rely on Conda packages, or need to manage dependencies beyond Python.

In general, we recommend using what your team or community uses. If you're
getting started on your own and aren't sure, uv is a good place to start.

## Working in a project

When working in a Python project, notebooks and scripts use a **shared
manifest** (a configuration file such as `pyproject.toml`) and a **shared
environment** prepared from its requirements.

Some tools also generate a **lockfile** that records the exact package versions
selected for those requirements.

For example, these two notebooks and their data-preparation script use the same
*project* requirements and environment:

=== "uv"

    ```text
    analysis/
    ├── pyproject.toml       # Project manifest
    ├── uv.lock              # Resolved dependency versions
    ├── prepare_data.py
    └── notebooks/
        ├── explore.py
        └── report.py
    ```

    With marimo included in the project's dependencies, open a notebook with:

    ```bash
    uv run marimo edit notebooks/explore.py
    ```

=== "Pixi"

    ```text
    analysis/
    ├── pyproject.toml       # Workspace manifest
    ├── pixi.lock            # Resolved dependency versions
    ├── prepare_data.py
    └── notebooks/
        ├── explore.py
        └── report.py
    ```

    Pixi calls a project a *workspace* and also supports `pixi.toml` as its manifest.

    With marimo included in the workspace's dependencies, open a notebook with:

    ```bash
    pixi run marimo edit notebooks/explore.py
    ```

Here, `uv run` and `pixi run` launch the marimo installed in the project's shared
environment. See [working in projects](projects.md) for setup with other package
managers and local development.

## Working in a sandbox

In [sandbox mode](sandboxes.md), each notebook contains its **own manifest** as inline script
metadata. marimo uses it to prepare an **isolated environment** for that
notebook, so notebooks can use different packages or versions without affecting
each other.

With uv or Pixi installed, you can open a notebook with:

=== "uv"

    ```bash
    uvx marimo edit --sandbox notebook.py
    ```

    uv is the default package manager for sandboxes and installs packages from PyPI.

=== "Pixi"

    ```bash
    pixi exec marimo edit --sandbox=pixi notebook.py
    ```

    Pixi supports Conda packages alongside PyPI packages.

[`uvx`](https://docs.astral.sh/uv/concepts/tools/) and [`pixi
exec`](https://pixi.prefix.dev/latest/reference/cli/pixi/exec/) install and
launch marimo. The `--sandbox` option tells marimo to prepare a separate
environment for the notebook's code.

Python version and package requirements are stored as **inline script metadata**
([PEP 723](https://peps.python.org/pep-0723/)) in a comment block at the top of the
notebook. The `dependencies` field lists Python packages, typically from PyPI.

```python title="notebook.py (header)"
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars",
#     "altair",
# ]
# ///
```

When you install Python packages through the editor, marimo updates both the
inline metadata and the notebook's environment.

Sandboxes don't inherit the surrounding project's packages. The same block can
include [uv- or Pixi-specific metadata](sandboxes.md#backend-specific-metadata)
for local packages, other package sources, or Conda dependencies. marimo passes
these settings to the selected backend when preparing the environment.

See [working in sandboxes](sandboxes.md) for managing dependencies and sharing
notebooks with any required data or source files.

!!! note "Dependency isolation"

    A notebook sandbox isolates installed packages. It does not restrict the
    notebook's access to your files or network; only run code you trust.

## Running notebooks as scripts

The same notebook can be edited interactively or executed from the terminal.
uv and Pixi can run notebooks using either project dependencies or inline
requirements. See [running notebooks as scripts](../scripts.md) for both workflows,
command-line arguments, and scheduled jobs.
