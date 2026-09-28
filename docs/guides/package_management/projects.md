# Working in projects

Notebooks in a project _share_ package requirements with other notebooks and
scripts. Those requirements live in a shared configuration file, such as
`pyproject.toml`, and all the notebooks in a project run in an environment with
those packages.

The [package management overview](index.md) compares shared projects with notebooks
that carry their own requirements.

## Set up your project { #open-a-notebook }

### With a project manager { #add-marimo-to-your-project }

Adding marimo to your project's requirements lets you open notebooks with the
same packages as the rest of your code. Choose your project manager below for
setup instructions.

=== "uv"

    If you're starting a new project, run `uv init` in your project directory
    or start from the [marimo uv starter template](https://github.com/marimo-team/marimo-uv-starter-template).
    To add marimo to the project's requirements, run:

    ```bash
    uv add marimo
    ```

    You can then open a notebook with the project's installed marimo and packages:

    ```bash
    uv run marimo edit notebook.py
    ```

    For a library where marimo is a development tool, use `uv add --dev marimo`.
    See [uv's project guide](https://docs.astral.sh/uv/guides/projects/) for more
    about managing project dependencies.

=== "Pixi"

    If you're starting a new project, run `pixi init --format pyproject` in your
    project directory to create a `pyproject.toml`. To add marimo to the
    project's requirements, run:

    ```bash
    pixi add --pypi marimo
    ```

    The `--pypi` flag installs marimo from PyPI. Pixi can also install Conda
    packages; see its guide to [managing Conda and PyPI dependencies](https://pixi.prefix.dev/latest/python/tutorial/#managing-both-conda-and-pypi-dependencies).

    You can then open a notebook with the project's installed marimo and packages:

    ```bash
    pixi run marimo edit notebook.py
    ```

=== "Poetry"

    If you're starting a new project, run `poetry init` in your project directory
    to create a `pyproject.toml`. To add marimo to the project's requirements, run:

    ```bash
    poetry add marimo
    ```

    You can then open a notebook with the project's installed marimo and packages:

    ```bash
    poetry run marimo edit notebook.py
    ```

    See [Poetry's project guide](https://python-poetry.org/docs/basic-usage/)
    for more about managing project dependencies.

Replacing `notebook.py` with `notebooks/` opens a directory of notebooks.
They use the same project environment unless you enable sandbox mode.

### With an environment you manage { #use-an-existing-environment }

With pip, or an environment you already manage, marimo is installed alongside
your notebook's packages. Activating the environment makes its `python` and
`marimo` commands available in your shell.

If you don't already have an environment, create one:

```bash
python -m venv .venv
```

Activate it in each new terminal session:

=== "macOS / Linux"

    ```bash
    source .venv/bin/activate
    ```

=== "Windows (PowerShell)"

    ```powershell
    .venv\Scripts\Activate.ps1
    ```

Then install marimo and your packages, and open a notebook:

```bash
python -m pip install marimo numpy
marimo edit notebook.py
```

To return to the notebook later, activate the same environment and run
`marimo edit notebook.py`.

If you use Conda, activate your Conda environment and
[install marimo there](../../getting_started/installation.md) instead.

Installing packages with pip does not automatically update the project's
requirements files, so the requirements need to be maintained separately for
others to install the same packages.

## Manage shared dependencies

The editor's [package panel](installing_packages.md) lets you add and remove
packages as you work. You can also use your project manager from the terminal:

=== "uv"

    ```bash
    uv add numpy
    uv remove numpy
    ```

=== "Pixi"

    ```bash
    pixi add numpy
    pixi remove numpy
    ```

=== "Poetry"

    ```bash
    poetry add numpy
    poetry remove numpy
    ```

Package changes apply to all notebooks using the shared environment. Sharing
the project's requirements file and any lockfile with your notebooks lets
collaborators install the recorded dependencies.

In a manually managed environment, packages can be installed with pip or your
environment's package manager.

## Import your project's code

Notebooks can import your project's Python package when it is installed in the
shared environment. An **editable installation** uses the source files directly,
so you can develop the package without reinstalling it after each change.

For example, a uv library project created with `uv init --lib my-library` can
have this layout:

```text
my-library/
├── pyproject.toml
├── uv.lock
├── src/
│   └── my_library/
│       └── __init__.py
└── notebooks/
    └── analysis.py
```

With marimo added to this project, `uv run marimo edit notebooks/analysis.py`
installs the library in editable mode and opens the notebook. Its cells can then
`import my_library`.

See [importing local modules](importing_local_code.md#importing-local-modules)
for other layouts and [module autoreloading](../editor_features/module_autoreloading.md)
for how marimo picks up source changes.

## Run notebooks as scripts

The same project requirements can be used to
[run notebooks as scripts](../scripts.md#running-in-a-project) without opening
the editor. That guide covers command-line arguments and scheduled execution.

## Keep standalone examples in a project

A repository can contain both project notebooks and notebooks with their own
requirements. For example, a tutorial might need extra packages that other
notebooks in the project don't use.

[Sandbox mode](sandboxes.md) prepares a separate environment for each notebook
without inheriting the project's packages. A notebook that uses your local
library needs to declare it, for example as an
[editable dependency](sandboxes.md#local-development-with-editable-installs).

A local path dependency still needs its source files when shared. A published
package or another accessible source lets others run the notebook without
cloning the surrounding repository.
