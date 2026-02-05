# Thumbnails

Generate screenshot-based thumbnail images for notebooks, used by [OpenGraph previews](opengraph.md) and cards in [gallery mode](../apps.md#gallery-mode).

```bash
marimo tools thumbnails generate notebook.py
```

## Output location

By default, thumbnails are written to:

```
<notebook_dir>/__marimo__/assets/<notebook_stem>/opengraph.png
```

This is the default OpenGraph thumbnail path used by [OpenGraph previews](opengraph.md).

## Requirements

!!! note "Requires Playwright"

    Thumbnail generation uses Playwright and Chromium:

    ```bash
    python -m pip install playwright
    python -m playwright install chromium
    ```

## Generate thumbnails

You can generate a thumbnail for a single notebook:

```bash
marimo tools thumbnails generate notebook.py
```

Or generate thumbnails for all notebooks in a directory:

```bash
marimo tools thumbnails generate folder/
```

When you pass a directory, marimo scans it for marimo notebooks and skips non-notebook files (for example `README.md`).

## Execution modes

By default, thumbnails are generated without executing the notebook (fast; no outputs). You can opt into execution if you want outputs included.

=== "No execution (default)"

    ```bash
    marimo tools thumbnails generate notebook.py
    ```

=== "Execute notebook"

    ```bash
    marimo tools thumbnails generate notebook.py --execute
    ```

=== "Execute in a sandbox"

    ```bash
    marimo tools thumbnails generate notebook.py --execute --sandbox
    ```

    !!! note "Requires uv"

        `--sandbox` runs the notebook in an isolated environment and installs dependencies from inline script metadata (PEP 723). See [Inlining dependencies](../package_management/inlining_dependencies.md).

!!! note "Sandbox only applies with execution"

    `--sandbox` requires `--execute`. In `--no-execute` mode, marimo does not run the notebook, so there are no dependencies to install.

!!! tip "Including code"

    In `--no-execute` mode, thumbnails always include code. When using `--execute`, add `--include-code` to show code alongside outputs.

## Overwriting and custom output paths

If a thumbnail already exists, marimo will skip it by default. To replace existing thumbnails:

```bash
marimo tools thumbnails generate notebook.py --overwrite
```

To write a thumbnail to a specific filename, use `--output` (single notebook only):

```bash
marimo tools thumbnails generate notebook.py --output thumbnail.png
```

## Tuning quality

For OpenGraph previews, the default viewport size is 1200x630. marimo also uses a default `--scale 2` so thumbnails are crisp at typical OpenGraph resolutions.

To increase output resolution, increase `--scale` (max 4):

```bash
marimo tools thumbnails generate notebook.py --scale 3
```

If thumbnails appear blank or partially rendered, increase `--timeout-ms` to wait longer before the screenshot:

```bash
marimo tools thumbnails generate notebook.py --timeout-ms 3000
```

## Passing arguments to notebooks

To pass CLI args through to the notebook, separate them with `--`:

```bash
marimo tools thumbnails generate notebook.py -- --foo 123
```

For more on passing values to notebooks, see [Command Line Arguments](../../api/cli_args.md).

