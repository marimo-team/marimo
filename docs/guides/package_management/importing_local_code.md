# Importing local code

Importing local Python code lets you reuse functions and classes across
notebooks. How you make the code available depends on where the files live
and whether the code is packaged.

## Import from the notebook's directory { #importing-local-modules }

Python files alongside a notebook can be imported directly:

```text
.
├── my_notebook.py
└── my_module.py
```

In a cell of `my_notebook.py`:

```python
import my_module
```

## Import from a source directory { #from-non-package-projects }

If notebooks and source code live in separate directories, tell marimo where
to find your modules. For example, a project might keep its code in `src/`:

```text
.
├── notebooks
│   └── my_notebook.py
├── pyproject.toml
└── src
    └── my_module.py
```

Add `src` to marimo's Python search path in `pyproject.toml`:

```toml title="pyproject.toml"
[tool.marimo.runtime]
pythonpath = ["src"]
```

The notebook can then `import my_module`. The `pythonpath` setting applies in
the editor, when serving the notebook as an app, and when running it as a script.

## Import a local package { #from-packages }

If your code is organized as a [Python package](https://docs.python.org/3/tutorial/modules.html#packages),
install it in the notebook's environment. For example, a package named
`my_package` might have this layout:

```text
.
├── notebooks
│   └── my_notebook.py
├── pyproject.toml
└── src
    └── my_package
        ├── __init__.py
        └── my_module.py
```

Once installed, the notebook can import from the package:

```python
from my_package import my_module
```

An **editable installation** uses your source files directly, so you don't need
to reinstall the package after each change. See
[working in projects](projects.md#import-your-projects-code) for setup in a
shared environment, or [sandbox configuration](sandboxes.md#local-development-with-editable-installs)
for declaring the local package in the notebook's own requirements.

!!! tip "Picking up source changes"

    [Module autoreloading](../editor_features/module_autoreloading.md) lets
    marimo pick up changes to imported code while your notebook is open.
