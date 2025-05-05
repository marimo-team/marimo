# Runtime configuration

Through the notebook settings menu, you can configure how and when marimo
runs cells.

<video controls width="100%" height="100%" align="center" src="/_static/docs-runtime-config.mp4"> </video>

## On startup

By default, marimo notebooks run automatically on startup; just how the command

```bash
python main.py
```

executes a script,

```bash
marimo edit notebook.py
```

executes the notebook.

Disable this behavior by unchecking "Autorun on startup".

_When sharing a notebook as an app with `marimo run`, this setting has
no effect._

## On cell change

By default, when a cell is run or a UI element is interacted with, marimo
automatically runs cells that reference any of its variables. **You can disable
automatic execution of cell's descendants in the notebook settings menu by
setting `"On cell change"` to `"lazy"`.**

When the runtime is lazy, running a cell marks affected cells as stale but
doesn't automatically run them. Lazy evaluation means cells are only run when
their outputs are needed. If you run a cell that has stale ancestors, those
ancestors will also run to make sure your cell doesn't use stale inputs. You
can always click the notebook run button or use the keyboard shortcut to run
all stale cells.

**When should I use lazy evaluation?** Choosing the lazy runtime can be helpful
when working on notebooks with expensive cells.

!!! tip "Tip: speed up expensive notebooks with marimo's smart caching"

    In addition to runtime configuration, marimo also provides [opt-in caching](../../api/caching.md)
    to help you work with expensive or side-effectful notebooks. marimo's
    can cache expensive functions in memory and expensive blocks of code to disk,
    letting you skip entire sections of your code and automatically loading
    variables in memory on notebook startup. Read our [caching
    guide](../../api/caching.md) to learn more.

_When sharing a notebook as an app with `marimo run`, this setting has
no effect._

## On module change

When module autoreloading is enabled, marimo automatically runs cells when you
edit Python files. Based on static analysis, the reloader only runs cells
affected by your edits. The reloader is recursive, meaning that marimo tracks
modifications for modules imported by your notebook's imported modules too.

!!! tip "Why autoreload?"

    Autoreloading enables a workflow that many developers find
    productive: develop complex logic in Python modules, and use the marimo
    notebook as a DAG or main script that orchestrates your logic.

Autoreloading comes in two types:

1. **autorun**: automatically re-runs cells affected by module modification.

<figure>
<video controls loop width="100%" height="100%" align="center" src="/_static/docs-module-reloading.mp4"> </video>
<figcaption align="center">When set to autorun, marimo's reloader automatically run cells when you edit Python files.</figcaption>
</figure>

2. **lazy**: marks cells affected by module modifications as stale, letting you know which cells need to be re-run.

<figure>
<video controls loop width="100%" height="100%" align="center" src="/_static/docs-module-reloading-lazy.mp4"> </video>
<figcaption align="center">When set to lazy, marimo's reloader marks cells as stale when you edit Python files.</figcaption>
</figure>

## Python path

By default, marimo will not add any additional directories to the Python path. This keeps the behavior of `marimo edit nb.py` and `python nb.py` consistent.

You can add directories to the Python path by setting the `pythonpath` key in the
runtime configuration. These directories will be added to the head of `sys.path`,
similar to how the `PYTHONPATH` environment variable works. This allows Python to
find and import modules from these directories.

```toml title="pyproject.toml"
[tool.marimo.runtime]
pythonpath = ["project/src"]
```

## Environment variables

### .env files

marimo supports loading environment variables from `.env` files. This is useful for managing configuration that should not be committed to version control, such as API keys or database credentials.

The `.env` next to your `pyproject.toml` is loaded by default. To configure multiple or a different location, you can specify them in your configuration:

```toml title="pyproject.toml"
[tool.marimo.runtime]
dotenv = [".env", ".env.testing"]
```

Environment variables from your `dotenv` will be surfaced in the UI when creating databases.
