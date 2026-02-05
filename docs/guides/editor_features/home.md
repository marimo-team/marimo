# Home page

Running `marimo edit` without a filename opens the home page, which lets you
browse and manage notebooks in a directory.

## Usage

```bash
# Open home page for current directory
marimo edit

# Open home page for a specific folder
marimo edit folder/
```

The home page shows all marimo notebooks in the directory, letting you:

- Open existing notebooks
- Create new notebooks
- See notebook metadata

## Sandboxed Home

You can run the home page in sandbox mode (called "Sandboxed Home"), where
each notebook gets its own isolated environment:

```bash
marimo edit --sandbox folder/
```

When using Sandboxed Home:

1. Each notebook runs in its own isolated environment
2. Dependencies are read from each notebook's [inline script metadata](../package_management/inlining_dependencies.md) (PEP 723)
3. Environments are created on-demand when you open a notebook

This is useful when you have a collection of notebooks with different
dependencies and want to keep them isolated from each other.

!!! note "Additional dependencies required"

    Sandboxed Home requires additional packages:

    ```bash
    uv add 'marimo[sandbox]'
    ```

    This installs `pyzmq` (for inter-process communication) and `uv`
    (for environment management).

### Using custom virtual environments

When using Sandboxed Home, you can specify an existing virtual environment
for a notebook instead of having marimo create one automatically.
This is configured using `[tool.marimo.venv]` in your script metadata:

```python
# /// script
# [tool.marimo.venv]
# path = "path/to/venv"      # relative or absolute path
# writable = false           # optional, default is false
# ///
```

!!! note "Sandboxed Home only"

    The `[tool.marimo.venv]` configuration only applies when using
    Sandboxed Home (`marimo edit --sandbox folder/`). For single notebooks,
    activate your virtual environment before running marimo:

    ```bash
    source path/to/venv/bin/activate
    marimo edit notebook.py
    ```

#### Configuration options

| Option | Description |
|--------|-------------|
| `path` | Path to the virtual environment (relative or absolute) |
| `writable` | Whether marimo can install packages into the venv (default: `false`) |

#### Behavior

| `writable` | marimo installed? | What happens |
|:-----------|:------------------|:-------------|
| `true` | - | marimo installs itself and required dependencies into the venv |
| `false` | Yes | Uses the venv as-is (warns if marimo version differs) |
| `false` | No | Injects `PYTHONPATH` for marimo (requires matching Python version) |

This is useful when:

- You have a conda or poetry environment you want to reuse
- You're working in a team with a shared environment
- You want notebooks in a folder to use different pre-configured environments
