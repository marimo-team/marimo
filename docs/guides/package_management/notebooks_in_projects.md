# Notebooks in existing projects

When working with notebooks in existing projects, there are two main approaches
depending on your needs:

1. **Sandbox notebooks** - Self-contained notebooks with isolated dependencies
2. **Project notebooks** - Notebooks that are part of your project's environment

marimo uses [PEP 723](https://peps.python.org/pep-0723/) inline script metadata
for sandboxing, managed by uv. While sandboxing is currently exclusive to the
uv package manager, other package managers may be supported in the future.

For project notebooks, marimo can be added as a project dependency where all
notebooks share the same environment defined in `pyproject.toml`. This approach
works with uv and other package managers (Poetry, Pixi, Hatch, etc.).

## Sandbox notebooks (recommended for libraries)

Sandbox notebooks use inline script metadata ([PEP
723](https://peps.python.org/pep-0723/)) to create isolated environments. This
is ideal when:

- Building examples for a library that users can run independently
- Creating notebooks that don't share dependencies with your main project
- Sharing self-contained notebooks that work anywhere

### Basic sandbox notebook

Sandbox notebooks can be created with:

```bash
marimo edit --sandbox notebook.py
```

When working in the notebook, marimo will automatically manage PEP 723 metadata
for you. This metadata makes the notebook self-contained, meaning you can
either come back later with marimo or run the notebook as a script directly
with uv:

```bash
marimo edit --sandbox notebook.py  # automatically loads deps and launches marimo
uv run notebook.py                  # run notebook as a script
```

### Developing against your local package

When developing library examples, tutorials, or exploratory code, it's often
useful to have notebooks that _use_ your library. In these cases, you can
create and version sandboxed notebooks with your library as an _editable_
install.

This approach lets you:

- Test your library changes immediately without reinstalling
- Add notebook-specific dependencies (like visualization or data processing tools) without polluting your library's requirements
- Create self-contained examples that users can run without your development dependencies

To add your library to a notebook, use uv:

```bash
uv add --script notebooks/notebook.py . --editable
```

This will produce a header that looks like:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "my-package",
#     "pandas",
#     "matplotlib",
# ]
#
# [tool.uv.sources]
# my-package = { path = "../", editable = true }
# ///
```

## Project notebooks

For notebooks that are integral to your project, you can manage everything
through your project's `pyproject.toml`. This approach uses a single
environment shared between your project and notebooks.

### Adding marimo to your project

```toml
[project]
name = "my-project"
dependencies = [
    "numpy",
    "requests",
]

[dependency-groups]
dev = [
    "marimo",
    "pytest",
]
```

Then work with notebooks using your project's environment:

```bash
# Using uv
uv run marimo edit notebooks/analysis.py

# Or activate the environment
source .venv/bin/activate
marimo edit notebooks/analysis.py
```

This approach:
- Uses a single environment for everything
- Shares dependencies between notebooks and your project
- Follows standard Python project practices

!!! note "Importing from other directories"
    If your notebooks need to import modules from directories outside your project, marimo supports configuring the Python path via `pyproject.toml`. However, when possible, it's preferred to avoid path manipulation. We recommend creating a package (`uv init --lib`) and including marimo as a development dependency. For multiple packages, consider configuring [uv workspaces](https://docs.astral.sh/uv/concepts/workspaces/). See the [runtime configuration guide](../configuration/runtime_configuration.md#python-path) for details.

## Examples

### Library with example notebooks

When building a library, use sandbox notebooks for examples that users can run
independently:

```
my-library/
├── pyproject.toml       # Library dependencies
├── src/
│   └── my_library/
└── examples/
    ├── quickstart.py    # Sandbox notebook
    └── advanced.py      # Sandbox notebook
```

Create example notebooks:
```bash
# Initialize the project
uv init --lib my-library && cd my-library

# Add marimo as development dependency
uv add --dev marimo

# Create a sandbox notebook
mkdir examples
uv run marimo edit --sandbox examples/quickstart.py

# Add your library as editable dependency
uv add --script examples/quickstart.py . --editable
```

### Data science project  

When notebooks are part of your analysis workflow, use project notebooks:

```
analysis-project/
├── pyproject.toml       # Project + marimo dependencies
├── README.md
├── main.py              # Created by uv init
└── notebook.py          # Your marimo notebook
```

Set up the project:
```bash
# Initialize project
uv init analysis-project && cd analysis-project

# Add marimo as a project dependency
uv add marimo pandas scikit-learn

# Edit notebooks using project environment
uv run marimo edit notebook.py
```

## Related guides

- [Using uv](using_uv.md) - Detailed guide on uv with marimo
- [Inlining dependencies](inlining_dependencies.md) - More on self-contained notebooks
- [Package management overview](index.md) - General package management in marimo
