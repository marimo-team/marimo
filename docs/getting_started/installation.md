# Installation

Before installing marimo, we recommend creating and activating a Python
[virtual environment](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments).

??? note "Setting up a virtual environment"

    Python uses virtual environments to minimize conflicts among packages.
    Here's a quickstart for `pip` users. If you use `conda`, please use a [`conda`
    environment](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands)
    instead.

    Run the following in the terminal:

    - create an environment with `python -m venv marimo-env`
    - activate the environment:
      - macOS/Unix: `source marimo-env/bin/activate`
      - Windows: `marimo-env\Scripts\activate`

    _Make sure the environment is activated before installing marimo and when
    using marimo._ Install other packages you may need, such as numpy, pandas, matplotlib,
    and altair, in this environment. When you're done, deactivate the environment
    with `deactivate` in the terminal.

    Learn more from the [official Python tutorial](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments).

/// admonition | Using uv?
    type: tip

[uv](https://github.com/astral-sh/uv) is a next-generation Python package
installer and manager that is 10-100x faster than pip, and also makes it easy
to install Python and manage projects. With `uv`, creating a virtual
environment is as easy as `uv venv`.
///

To install marimo, run the following in a terminal:

/// tab | install with pip

```bash
pip install marimo
```

///

/// tab | install with uv

```bash
uv pip install marimo
```

///

/// tab | install with conda

```bash
conda install -c conda-forge marimo
```

///

To check if the install worked, run

```bash
marimo tutorial intro
```

A tutorial notebook should open in your browser.

/// admonition | Installation issues?
    type: note

Having installation issues? Reach out to us [at GitHub](https://github.com/marimo-team/marimo/issues) or [on Discord](https://marimo.io/discord?ref=docs).
///
