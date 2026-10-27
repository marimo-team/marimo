# Language Server Protocol (LSP)

The marimo editor supports the Language Server Protocol (LSP) to provide enhanced code intelligence features like:

- Code completion
- Hover information
- Go to definition
- Error checking and diagnostics

Multiple language servers can be run simultaneously. When
enabled, their results are merged — for example, you can
get completions from pylsp and diagnostics from basedpyright at the same time.

If you launch marimo with `--sandbox` (e.g. `marimo edit --sandbox`, `marimo
new --sandbox`, `marimo run --sandbox`), language servers are resolved
differently than without it; see [Sandbox mode](#sandbox-mode-sandbox) below.

## Supported language servers

### pylsp (python-lsp-server)

The core Python language server providing completions, hover, go-to-definition,
diagnostics, code actions, rename, and signature help.

**Install:**

```bash
pip install "marimo[lsp]"
# or
uv add "marimo[lsp]"
# or
conda install -c conda-forge python-lsp-server python-lsp-ruff
```

This installs:

- [`python-lsp-server`](https://github.com/python-lsp/python-lsp-server): The core Python language server
- [`python-lsp-ruff`](https://github.com/python-lsp/python-lsp-ruff): Ruff integration for fast linting

You may optionally install other `pylsp` plugins (e.g. `pylsp-mypy`).

**Configuration:**

```toml title="pyproject.toml"
[tool.marimo.language_servers.pylsp]
enabled = true               # Enable/disable pylsp
enable_mypy = true           # Type checking with mypy (enabled by default, if installed)
enable_ruff = true           # Linting with ruff (enabled by default, if installed)
enable_flake8 = false        # Linting with flake8
enable_pydocstyle = false    # Check docstring style
enable_pylint = false        # Linting with pylint
enable_pyflakes = false      # Syntax checking with pyflakes
```

### basedpyright

A type checker for Python built on Pyright. In marimo, basedpyright is used
for **diagnostics only** (type checking errors and warnings).

**Install:**

```bash
uv pip install basedpyright
```

**Configuration:**

```toml title="pyproject.toml"
[tool.marimo.language_servers.basedpyright]
enabled = true
```

See the [basedpyright docs](https://docs.basedpyright.com) for more information.

### ty

A type checker for Python from [Astral](https://astral.sh/) (the creators of
Ruff). In marimo, ty is used for **diagnostics only**.

**Install:**

```bash
uv pip install ty
```

**Configuration:**

```toml title="pyproject.toml"
[tool.marimo.language_servers.ty]
enabled = true
```

See the [ty docs](https://docs.astral.sh/ty/features/language-server/) for more information.

### pyrefly

A type checker for Python from Meta. Pyrefly provides completions, hover,
go-to-definition, and diagnostics.

**Install:**

```bash
uv pip install pyrefly
```

**Configuration:**

```toml title="pyproject.toml"
[tool.marimo.language_servers.pyrefly]
enabled = true
```

See the [pyrefly docs](https://pyrefly.org/en/docs/IDE-features/) for more information.

### GitHub Copilot

AI-powered code completions via the GitHub Copilot language server. Copilot is
configured separately from the other language servers through the completion
settings.

**Configuration:**

```toml title="pyproject.toml"
[tool.marimo.completion]
copilot = "github"
```

See the [AI completion guide](ai_completion.md#github-copilot) for
more details on Copilot setup and configuration.

## Using multiple language servers

You can enable multiple language servers at once. marimo uses a federated
architecture that merges results from all active servers. For example, you might
use pylsp for completions and code actions while relying on basedpyright or ty
for stricter type-checking diagnostics.

## Diagnostics

Diagnostics from all language servers can be toggled globally:

```toml title="pyproject.toml"
[tool.marimo.diagnostics]
enabled = true               # Show diagnostics in the editor
```

## WebAssembly

Language servers are not available when running marimo in WebAssembly.

## Sandbox mode (`--sandbox`)

Passing `--sandbox` to any marimo command that starts the editor (e.g. `marimo
edit --sandbox`) relaunches
the editor itself inside an ephemeral environment managed by `uv` (or
`pixi`). That environment is built from the Python environment you ran
`marimo` from, with marimo's own `lsp` extra layered on top automatically.
This matters for which language servers are available:

- **pylsp** works out of the box in sandbox mode, since `python-lsp-server`
  and `python-lsp-ruff` are installed automatically as part of the `lsp`
  extra.
- **basedpyright**, **ty**, and **pyrefly** are standalone tools, not part of
  marimo's `lsp` extra, so the sandboxed editor does not install them for
  you. They must already be importable from the environment you launched
  `marimo` from. Installing them into the *notebook's* own sandboxed
  environment has no effect here — that environment is used by the kernel
  subprocess that runs your notebook's code, not by the editor process that
  hosts the language servers.

To make one of these available in sandbox mode, add it with `--with` on the
command that launches marimo itself, so it's present in the environment the
sandboxed editor is built from:

```bash
uv run --with basedpyright marimo edit --sandbox notebook.py
uv run --with ty marimo edit --sandbox notebook.py
uv run --with pyrefly marimo edit --sandbox notebook.py
```

`ty` additionally ships a standalone CLI binary, so installing it with `uv
tool install ty` and having it on `PATH` also works, since marimo falls back
to checking `PATH` for `ty` specifically. `basedpyright` and `pyrefly` have
no such fallback and must be importable.

## Troubleshooting

If you encounter issues with a language server:

1. Make sure you've installed the required dependencies with `uv pip install "marimo[lsp]"`
2. For basedpyright, ty, and pyrefly, ensure [Node.js](https://nodejs.org/) is installed
3. If you're using `marimo edit --sandbox`, see [Sandbox mode](#sandbox-mode-sandbox) above — the tool must be importable from the environment marimo was launched from, not the notebook's own environment
4. Check if the language server is enabled in your configuration
5. Try restarting the marimo server
6. Check the terminal for error messages or the log files in your marimo log directory (e.g. `~/.cache/marimo/logs/`)
