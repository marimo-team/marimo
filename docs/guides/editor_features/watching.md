# Using your own editor

While we recommend using the [marimo editor](index.md),
we understand that you may prefer to use your own. marimo provides a
`--watch` flag that watches your notebook file for changes, syncing them to
the marimo editor or running application. This lets you edit your notebook
using an editor of your choice, like neovim, VSCode, Cursor, or PyCharm, and
have the changes automatically reflected in your browser.

!!! tip "Install watchdog for better file watching"
    For better performance, install [watchdog](https://pypi.org/project/watchdog/).
    Without watchdog, marimo resorts to polling.

## marimo's file format

!!! tip "File format tutorial"

    Run `marimo tutorial fileformat` at the command line for a full guide.

marimo stores notebooks as Python files.  Cells are stored
as functions, decorated with`@app.cell`; you can optionally give cells names in
the editor UI or by editing the notebook file.

```python
@app.cell
def memorable_cell_name(auto, determined, references):  # signature denotes cell references
    computed_value = auto + determined + references
    "hello!"                                            # final statement is the visual output
    return computed_value                               # return denotes cell definitions
```

!!! note "Cell signature and returns"

    Don't worry about maintaining the signatures of cells and their return
    values; marimo will handle this for you.

### Exposing functions and classes top-level

You can expose top-level functions and classes in your
notebook, so that other Python modules can import them:

```python
from my_notebook import my_function, MyClass
```

Top-level functions are added to a notebook using the `@app.function`
decorator, and classes with `@app.class_definition`; these appear in your
notebook as cells with just a function or class definition. These functions and
classes must be pure, closing over only other pure functions and classes, or
imports and constants defined in an `app.setup` `with` block.

Here is a complete example that you can copy/paste and run locally:


```python
import marimo

app = marimo.App()

with app.setup:
    # These symbols can be used by top-level functions and classes
    # (as well as by regular cells)
    import numpy as np

    CONSTANT: int = 1

@app.function
def my_function(x: np.ndarray):
    return np.mean(x) + CONSTANT

@app.class_definition
class MyClass:
    ...

@app.cell
def _():
    my_function(np.random.randn(2, 2))
    return

if __name__ == "__main__":
    app.run()
```

For more details see the [guide on reusable functions and classes](../reusing_functions.md).

### Types and autocompletion

Add type hints to your variables, and marimo will carry over these type hints
to cells where these variables are used. This, combined with importing modules
in the setup cell (see below for an example), makes it possible for your editor
to give completions on the references of your cell.


For example:

```python
# setup cell
import numpy as np

# cell 1
x: np.ndarray

# cell 2
np.mean(x)
```

will be serialized as

```python
import marimo

app = marimo.App()

with app.setup:
    import numpy as np

@app.cell
def _():
    x: np.ndarray
    return x,

@app.cell
def _(x: np.ndarray):
    np.mean(x)

if __name__ == "__main__":
    app.run()
```

### As markdown

!!! tip "Markdown File format tutorial"
    Run `marimo tutorial markdown-format` at the command line for a full guide.

marimo notebooks can also be stored as Markdown files. This is a good option
for prose heavy text, and can be easy to navigate and edit in external editors.
To convert a marimo notebook to markdown, use

```
marimo export md notebook.py -o notebook.md
```

at the command-line, or rename your file to have an `.md` extension in the notebook editor.

marimo conforms to standard markdown document format, and will render most
places like Github. Metadata in this file format is saved in the frontmatter,
which marimo may use for information like
[sandboxing](../package_reproducibility.md), and the marimo version. All other
fields are kept, but ignored.

For execution, marimo extracts code fences that contain `marimo` in braces. For
instance `python {marimo}`, `{marimo}` or `{.marimo .python}`. The marimo
editor uses `python {.marimo}` which is Pandoc compatible, and correctly
processed by text highlighters.

````markdown
---
title: My Notebook
marimo-version: 0.0.0
description: A notebook with a description
---

# Just a notebook

```python {.marimo}
print("Hello World!")
```
````

marimo's markdown format can be used with a [`mkdocs
plugin`](https://github.com/marimo-team/mkdocs-marimo) and
[`Quarto`](https://github.com/marimo-team/quarto-marimo).

Note that the markdown format is not as fully featured as the Python format.
Reactive tests will not work, markdown notebooks cannot be imported or used as
a library, and they cannot be run as scripts.

## Watching for changes to your notebook

### `marimo edit --watch`

When you run `marimo edit` with the `--watch` flag, the marimo server
will open your notebook in the browser and watch the underlying notebook
file for changes. When you make changes to the notebook file, they will be
streamed to the marimo editor in the browser.

By default, synced code will not be executed automatically, with cells marked
as stale instead. Run all stale cells with the marimo editor's "Run" button, or
the [`runStale` hotkey](hotkeys.md), to see the new outputs.

If you want to run all affected cells automatically when you save, change the
`runtime` config in your `pyproject.toml` file.

```toml
[tool.marimo.runtime]
watcher_on_save = "autorun"
```

### `marimo run --watch`

When you run `marimo run` with the `--watch` flag, whenever the file watcher
detects a change to the notebook file, the application will be refreshed. The
browser will trigger a page refresh to ensure your notebook starts from a fresh
state.

## Watching for changes to other modules

marimo can also watch for changes to Python modules that your notebook imports,
letting you edit auxiliary Python files in your own editor as well. Learn how
to enable this feature in our [Module Autoreloading
Guide](module_autoreloading.md)

## Watching for data changes

!!! note
    Support for watching data files and automatically refreshing cells that
    depend on them is not yet supported. Follow along at
    <https://github.com/marimo-team/marimo/issues/3258> and let us know
    if it is important to you.

## Hot-reloading WebAssembly notebooks

Follow these steps to develop a notebook using your own editor while previewing
it as a [WebAssembly notebook](../wasm.md) in the browser. This lets you take
advantage of local development tools while seeing the notebook as it appears
when deployed as a WebAssembly notebook.

```bash
# in one terminal, start a watched edit (or run) session
marimo edit notebook.py --watch

# in another terminal
marimo export html-wasm notebook.py -o output_dir --watch

# in a third terminal, serve the WASM application
cd path/to/output_dir
python -m http.server  # or a server that watches for changes
```
