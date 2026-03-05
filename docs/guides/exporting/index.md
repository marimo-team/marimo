# Export to other formats

Export marimo notebooks to other file formats at the command line using

```bash
marimo export
```

/// tip | Looking to share notebooks online?
For sharing interactive notebooks on the web, consider using [molab](../molab.md) — the easiest way to share marimo notebooks. For other publishing options, see [Publish to the web](../publishing/index.md).
///

## Available formats

| Format | Command | Description |
|--------|---------|-------------|
| [Static HTML](static_html.md) | `marimo export html` | Non-interactive HTML snapshot |
| [PDF](pdf.md) | `marimo export pdf` | PDF document or slide deck |
| [Jupyter notebook](jupyter_notebook.md) | `marimo export ipynb` | Jupyter `.ipynb` file |
| [Python script](python_script.md) | `marimo export script` | Flat `.py` script in topological order |
| [Markdown](markdown.md) | `marimo export md` | Markdown with code blocks |
| [WebAssembly HTML](webassembly_html.md) | `marimo export html-wasm` | Self-contained, interactive HTML powered by WebAssembly |
| [Session snapshot](sessions.md) | `marimo export session` | Serialized session snapshot (JSON) |

!!! note "Note"

    If any cells error during the export process, the status code will be non-zero. However, the export result may still be generated, with the error included in the output.
    Errors can be ignored by appending `|| true` to the command, e.g. `marimo export html notebook.py || true`.
