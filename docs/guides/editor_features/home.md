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

You can open a directory in sandbox mode, giving each notebook its own isolated
environment:

=== "uv"

    ```bash
    marimo edit --sandbox folder/
    ```

=== "Pixi"

    ```bash
    marimo edit --sandbox=pixi folder/
    ```

Each environment is prepared from the notebook's requirements when you open it.
See [working in sandboxes](../package_management/sandboxes.md#open-a-directory-of-notebooks)
for setup with uv or Pixi.

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

This configuration also applies when editing a single file with
`marimo edit --sandbox notebook.py`. The configured environment takes precedence
over creating an environment from inline requirements. To use an activated
environment directly, see
[using an existing environment](../package_management/projects.md#use-an-existing-environment).

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
