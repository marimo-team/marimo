# Importing packages

By default, marimo searches for packages in the [virtual
environment](https://docs.python.org/3/tutorial/venv.html) it was started in.
For example, if you run

```console
source /path/to/venv/bin/activate
marimo edit my_notebook.py
```

you'll be able to import packages installed in the environment you just
activated. You'll also be able to install packages into this environment using
the marimo editor's [package management UI](installing_packages.md).

!!! question "Using uv?"

    See our [uv guide](using_uv.md) for details on how to use marimo as part of
    uv projects or as self-contained scripts.
    
## Inlining dependencies

As an alternative to manually creating and managing a virtual environment,
you can let marimo manage virtual environments for you, on a per-notebook
basis.

If you create a notebook with the `--sandbox` flag —

```console
marimo edit --sandbox my_notebook.py
```

— marimo will start your notebook in an isolated environment and keep track of
the dependencies you install from the editor. These dependencies are inlined in
the notebook file, so that the next time you run the notebook,
marimo will run it in an isolated environment with just those dependencies.

See our guide on [inlining dependencies](inlining_dependencies.md)
to learn more.

!!! question "What about kernels?"

    Unlike Jupyter, marimo does not have a concept of "kernels"; notebooks simply
    use the active virtual environment.
    
    The main feature of kernels is to allow different notebooks to depend on
    different packages, even within the same project. marimo's package sandbox
    provides this functionality, while also being far simpler to use than
    custom kernels.


## Importing local modules

marimo resolves imports just as Python does: by searching for packages
in the directories listed in `sys.path`. That means that in addition to the
virtual environment, marimo will search for modules in the directory in which
the notebook lives. For example, when you run

```console
marimo edit /path/to/notebook_dir/notebook.py
```

marimo will look for modules in `/path/to/notebook_dir`. However, this means
that you may need to take additional steps to import modules that live outside
this directory. What steps you take depends on whether your code is organized
as a Python package.

!!! tip "Remember: notebooks are just Python programs"

    In the examples below, notebooks are stored in a separate notebooks
    directory, which is traditional. However, since marimo notebooks are just
    Python modules, you can just as well include them in your `src/` directory
    alongside other Python modules.


### From non-package projects

You can configure the Python path to accommodate directory structures that look like this:

```
.
├── notebooks
│   └── my_notebook.py
├── pyproject.toml
└── src
    └── my_module.py
```

In particular, to make `import my_module` work when running

/// tab | edit

```console
marimo edit notebooks/my_notebook.py
```

///

/// tab | run

```console
marimo run notebooks/my_notebook.py
```

///

/// tab | script

```console
python notebooks/my_notebook.py
```

///

add the following configuration to your `pyproject.toml`:

```toml title="pyproject.toml"
[tool.marimo.runtime]
pythonpath = ["src"]
```

### From packages

!!! question "New to Python packages?"

    A [Python package](https://docs.python.org/3/tutorial/modules.html#packages) is a
    way of structuring Python source files so that the collection of files can
    be installed in an environment, imported using "dot" notation like
    `from my_package.my_module import my_function`, and optionally uploaded
    to package registries like PyPI.

    If you are new to packages, and find you need to create one, we recommend
    using [uv](https://docs.astral.sh/uv/) (`uv init --package`).

A package has a directory structure like this:

```
.
├── notebooks
│   └── my_notebook.py
├── pyproject.toml
└── src
    └── my_package
        ├── __init__.py
        └── my_module.py
```

Say `my_notebook` has a cell with

```python
from my_package import my_module
```

Provided that

/// tab | edit

```console
marimo edit notebooks/my_notebook.py
```

///

/// tab | run

```console
marimo run notebooks/my_notebook.py
```

///

/// tab | script

```console
python notebooks/my_notebook.py
```

///

is run from an environment in which your package is installed, marimo
will import `my_module` without issue.

For example, if you are using `uv`, simply run

```console
uv run --with marimo marimo edit notebooks/my_notebook.py
```
