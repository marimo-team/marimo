# Language Server Protocol (LSP)

The marimo editor supports the Language Server Protocol (LSP) to provide enhanced code intelligence features like:

- Code completion
- Hover information
- Go to definition
- Error checking and diagnostics

## Installation

LSP support requires additional dependencies. You can install them with:

```bash
pip install "marimo[lsp]"
# or
uv add "marimo[lsp]"
# or
conda install -c conda-forge python-lsp-server python-lsp-ruff
```

This will install the necessary packages including:

- [`python-lsp-server`](https://github.com/python-lsp/python-lsp-server): The core Python language server
- `python-lsp-ruff`: Ruff integration for fast linting

You may optionally install other `pylsp` plugins.

!!! note "Other Python Language Servers"

    Support for other Python language servers is planned for future releases.

## Configuration

LSP support can be configured in your `pyproject.toml` file.

```toml title="pyproject.toml"

# Language server configuration
[tool.marimo.language_servers.pylsp]
enabled = true               # Enable/disable the Python language server
enable_mypy = true           # Type checking with mypy (enabled by default, if installed)
enable_ruff = true           # Linting with ruff (enabled by default, if installed)
enable_flake8 = false        # Linting with flake8
enable_pydocstyle = false    # Check docstring style
enable_pylint = false        # Linting with pylint
enable_pyflakes = false      # Syntax checking with pyflakes

# Diagnostics configuration
[tool.marimo.diagnostics]
enabled = true               # Show diagnostics in the editor
```

## WebAssembly

Language Servers are not available when running marimo in WebAssembly.

## Troubleshooting

If you encounter issues with the language server:

1. Make sure you've installed the required dependencies with `pip install "marimo[lsp]"`
2. Check if the language server is enabled in your configuration
3. Try restarting the marimo server
4. Check the terminal for any error messages
