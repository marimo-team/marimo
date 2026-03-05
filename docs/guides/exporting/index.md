# Export to other formats

Export marimo notebooks to other file formats from the browser editor. Notebooks can
also be exported to other formats at the command-line with:

```bash
marimo export
```

/// tip | Looking to share notebooks online?
For sharing interactive notebooks on the public web, consider using [molab](../molab.md), our free cloud-hosted notebook platform.
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
