# OpenGraph previews

marimo can attach OpenGraph metadata to notebooks for:

- previews in the `marimo run <directory>` [gallery](../apps.md#gallery-mode)
- link previews (OpenGraph tags in the notebook HTML)

You configure this metadata in your notebook file using inline script metadata (PEP 723), under `[tool.marimo.opengraph]`.

## Configure metadata

Add an `[tool.marimo.opengraph]` section to your script metadata:

```python
# /// script
# [tool.marimo.opengraph]
# title = "My notebook"
# description = "An interactive marimo app."
# ///
```

Available fields:

- `title`: Title used in previews (defaults to a title-cased filename).
- `description`: Short description shown in previews.
- `image`: Optional thumbnail image. Must be either:
  - an HTTPS URL, or
  - a notebook-relative path under `__marimo__/` (for example, `__marimo__/assets/my_notebook/opengraph.png`).

If you generate thumbnails to the default location (see below), you typically do not need to set `image`: marimo will automatically use `__marimo__/assets/<notebook_stem>/opengraph.png` when it exists.

!!! note "Relative image paths"

    For security, marimo only serves notebook-relative `image` paths from the notebook's `__marimo__/` directory.

## Thumbnails

If you do not provide an `image`, marimo can still serve a deterministic placeholder thumbnail. If a screenshot-based thumbnail exists at the default location, marimo will automatically use it.

The default thumbnail location is:

```
__marimo__/assets/<notebook_stem>/opengraph.png
```

To generate these thumbnails, use:

```bash
marimo tools thumbnails generate notebook.py
marimo tools thumbnails generate folder/
```

For execution and sandbox options (and for Playwright installation instructions), see [Thumbnails](../cli_tools/thumbnails.md).

## Dynamic metadata

For dynamic previews, you can provide a generator function in script metadata. Generators must be [top-level functions](../reusing_functions.md) (decorated with `@app.function`) and cannot depend on values defined in regular cells, so that they can be safely executed in the marimo CLI without running the whole notebook.

In script metadata, point `generator` at the name of a function defined in the notebook:

```python
# /// script
# [tool.marimo.opengraph]
# description = "This description is static."
# generator = "generate_opengraph"
# ///
```

Then define the generator in a notebook cell:

/// marimo-embed
```python
@app.function
def generate_opengraph(context, parent):
    import datetime as dt
    from pathlib import Path
    from urllib.parse import quote_plus

    # Merge behavior: we return `title` and `image`, so the static `description` stays intact (it's already in `parent`).
    stem = Path(context.filepath).stem
    label = quote_plus(f"{stem} {dt.datetime.now().isoformat()}")
    title = f"{parent.title} (Dynamic)" if parent.title else "Dynamic OpenGraph"
    return {
        "title": title,
        "image": f"https://placehold.co/1200x630/png?text={label}",
    }
```
///

The generator return value is merged on top of the resolved "parent" metadata (declared fields + defaults). Any fields not returned by the generator are inherited from `parent`.

### Generator signatures

The generator may accept 0, 1, or 2 positional arguments:

- `generate_opengraph()`
- `generate_opengraph(context)`
- `generate_opengraph(context, parent)`

Type hints:

- `context`: `marimo._metadata.opengraph.OpenGraphContext`
- `parent`: `marimo._metadata.opengraph.OpenGraphMetadata`

`context` is an object with useful runtime information:

- `context.filepath`: absolute path to the notebook
- `context.file_key`: file router key (often a workspace-relative path)
- `context.base_url`: server base URL (when running with `marimo run`)
- `context.mode`: `"run"` or `"edit"`

The generator may return:

- an `OpenGraphMetadata` instance
- a `dict` with any of `title`, `description`, and `image`
- `None` (to leave the parent metadata unchanged)
