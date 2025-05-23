# Using uv

[uv](https://docs.astral.sh/uv/) is an extremely fast Python package and
project manager: you can use it to install packages, manage the dependencies
of Python projects, and run scripts. While marimo supports all major package
managers, it integrates especially tightly with uv. In particular, marimo's
package sandbox feature, which lets you [inline
dependencies](inlining_dependencies.md) in notebook files, requires uv.

!!! note "No prior knowledge required"

    This guide teaches you the basics of using `uv` with marimo. It assumes zero
    familiarity with `uv`.

You can manage your notebooks' dependencies in three different ways:

1. inline dependencies: [inlining dependencies](inlining_dependencies.md) in notebook files, using `marimo edit --sandbox notebook.py`
2. projects: using a `uv` project , which define dependencies declaratively in a `pyproject.toml`
   file;
3. non-project environment: dependencies are imperatively installed

We'll walk through each of these three ways in this guide.

## Using inline dependencies

The easiest way to get started is to use marimo's [package sandbox
feature](inlining_dependencies.md), which manages your dependencies for you.
Create or edit your notebook with [`uvx`
command](https://docs.astral.sh/uv/concepts/tools/#the-uv-tool-interface),
making sure to include the `--sandbox` flag:

<!-- TODO propagating marimo version into the script metadata --> 

```console
uvx marimo edit --sandbox my_notebook.py
```

This command installs marimo in a temporary environment, activates it, then
runs your marimo notebook. The `--sandbox` flag what tells marimo to keep
track of your dependencies and store them in the notebook file. If there are
any dependencies already tracked in the file, this command will download
them and install them in the environment.

Run sandboxed notebooks as scripts with

```console
uv run my_notebook.py
```

### From URLs

You can also upload sandboxed notebooks to the web, such as on GitHub, and have others run
them locally with a single command:

```
uvx marimo edit --sandbox https://gist.githubusercontent.com/kolibril13/a59135dd0973b97d488ba21c650667fe/raw/5f98021b5d3c024d5827fa9464787517495178b4/marimo_minimal_numpy_example.py
```

**Note:**

1. This command will run code from a URL. Make sure you trust the source before proceeding.
2. Upon execution, you’ll be prompted:
   ```
   Would you like to run it in a secure docker container? [Y/n]:
   ```
   To proceed securely, ensure you have [Docker](https://www.docker.com/) installed and running, then press `Y`.


To learn more, read our full guide on using [inline dependencies](inlining_dependencies.md).

## Using uv projects

A [`uv` project](https://docs.astral.sh/uv/guides/projects/) is a directory in which you can store Python code, including
notebooks, alongside a pyproject.toml file that declares the project's
dependencies.

### Creating a project

Create a project with `uv init`:

```console
uv init hello-world
cd hello-world
```

!!! tip "Starter template"

    Get started quickly by cloning our [starter template](https://github.com/marimo-team/marimo-uv-starter-template).
    

This creates a pyproject.toml and some starter code.

Next, add marimo to your project:

```console
uv add marimo
```

??? note "Omitting marimo from your project"

    Adding marimo to your project is optional. Instead, you can
    run marimo in a temporary environment that has access to
    your project's dependencies using `uv run --with marimo marimo edit`.

### Running marimo

Once you've added marimo, use the `uv run` command
to run the version of marimo installed in your project:

```console
uv run marimo edit my_notebook.py
```

Starting marimo in this way will let marimo import any of the packages
installed in your project.

**Scripts.** Run marimo notebooks as scripts with

```console
uv run my_notebook.py
```

which will run your notebook in an environment containing your project dependencies.

### Adding and removing dependencies

#### Using the uv command-line

Use `uv add` to add dependencies:

```console
uv add numpy
```

You can also specify a version

```console
uv add numpy==2.26
```

Remove packages with `uv remove`:

```console
uv remove numpy
```

#### Using the marimo editor

If you started marimo with `uv run marimo edit`, the marimo editor's [package
management features](installing_packages.md) will add and remove packages from
your pyproject.toml, so there's no need to use the `uv` command-line if you
don't want to.

## Using marimo in a non-project environment

If you are used to a venv and pip based workflow, you can use the `uv venv` and
`uv pip` commands for a similar but more performant experience:

* `uv venv` creates a virtual environment in the current directory, at `.venv`
* `uv pip` lets you install and uninstall packages in the venv

### Example

=== "macOS and Linux"

    ```console
    $ uv venv
    $ uv pip install numpy
    $ uv pip install marimo
    $ .venv/bin/marimo edit
    ```

=== "Windows"

    ```pwsh-session
    PS> uv venv
    PS> uv pip install numpy
    PS> uv pip install marimo
    PS> .venv\Scripts\marimo edit
    ```

From here, `import numpy` will work within the notebook, and marimo's UI installer will add
packages to the environment with `uv pip install` on your behalf.
