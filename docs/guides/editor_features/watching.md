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

## marimo's File format

### Python file format

!!! tip "File format tutorial"

    Run `marimo tutorial fileformat` at the command line for a full guide.

marimo stores notebooks as Python files with cell definitions. Cells are stored
as functions, decorated with`@app.cell`; you can optionally give cells names in
the editor UI or by editing the notebook file.

```python
@app.cell
def memorable_cell_name(auto, determined, references):  # signature denotes cell inputs
    computed_value = auto + determined + references
    "hello!"                                            # final statement are outputted
    return computed_value                               # return denotes cell outputs
```

!!! note "Cell signature and returns"

    Don't worry about maintaining the signatures of cells and their return
    values; marimo will handle this for you.

You may also expose imports, and top-level functions and classes in your
notebook. Functions must be decorated with `@app.function`, and classes with
`app.class_definition`. These functions and classes must be pure, closing over
only other pure functions and classes or imports and constants defined in
an `app.setup` with block:

For more details see the [library guide](../reusing_functions.md).

```python
with app.setup:
    CONSTANT: int = 1
    import marimo as mo

@app.function
def my_function(x): ...

@app.class_definition
class MyClass: ...
```

!!! question "Want to use your own LSP for typing?"
    Explicitly typing your definitions will let marimo carry the annotations
    into function signatures. For instance

```python
# cell 1
x: int
y: str

# cell 2
z = f"{x} & {y}"
```

will be serialized as

```python
@app.cell
def cell_1():
    x: int
    y: str
    return x, y

@app.cell
def cell_2(x: int, y: str):
    z = f"{x} & {y}"
```

### Markdown file format

!!! tip "Markdown File format tutorial"
    Run `marimo tutorial markdown-format` at the command line for a full guide.

marimo notebooks can also be stored as Markdown files. This is a good option
for prose heavy text, and can be easy to navigate and edit in external editors.

marimo conforms to standard markdown document format, and will render most
places like Github.
Metadata in this file format is saved in the frontmatter, which marimo may use
for information like [sandboxing](../package_reproducibility.md), and the
marimo version. All other fields are kept, but ignored.

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
plugin`](https://github.com/marimo-team/mkdocs-marimo), and
[`Quarto`](https://github.com/marimo-team/quarto-marimo).

Note, there is some feature loss in this format. Reactive tests will not work,
and the notebooks cannot be imported or used as a library.

## `marimo edit --watch`

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

## `marimo run --watch`

When you run a notebook with the `--watch` flag, whenever the file watcher
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
    depend on them is coming soon. Follow along at
    <https://github.com/marimo-team/marimo/issues/3258>

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
