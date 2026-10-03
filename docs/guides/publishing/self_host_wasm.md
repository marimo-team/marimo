# Self-host WebAssembly notebooks

As an alternative to [GitHub Pages](github.md#publish-to-github-pages), it is possible to self-host
exported [WebAssembly notebooks](../wasm.md):

-   [Export to WASM HTML](../exporting/webassembly_html.md).
-   Serve the exported file over HTTP.
-   Serve the assets in the `assets` directory, next to the HTML file.
-   Possibly configure your web server to support serving `application/wasm/`
    files with the correct headers.

## Exporting for offline use

Use `--offline` to download the Python runtime and notebook packages alongside
the exported HTML.

Offline export requires [Playwright for Python and its Chromium browser](https://playwright.dev/python/docs/library#installation).
Use the Python environment where marimo is installed for all three commands:

```bash
python -m pip install playwright
python -m playwright install chromium
python -m marimo export html-wasm notebook.py -o dist --offline
```

The export requires internet access or
[package mirrors](#using-package-mirrors). Playwright runs Pyodide to resolve
browser-compatible dependencies without executing notebook cells. The result
can be served from a local HTTP server or copied to a static host:

```text
dist/
├── index.html
├── assets/
├── pyodide/
├── lockfile/
└── packages/
```

The HTML uses relative URLs for the bundled runtime, lockfile, and package
index, so the directory can be moved to another host or URL prefix. The
`packages` directory includes transitive dependencies, packages inferred from
imports that are available in Pyodide, and dependencies declared in
[inline script metadata](../package_management/sandboxes.md).
Declare PyPI dependencies in that metadata, including packages installed
dynamically by the notebook.

`--offline` bundles Python dependencies. Data files, remote API calls, and
JavaScript assets fetched by notebook code or widgets still need local
alternatives. Serve the export over HTTP even when using it offline.

Without `--offline`, the browser uses the default hosted Python runtime and
package sources.

### Using package mirrors

Pass `--pyodide-index-url` and `--pypi-index-url` to build the offline export
from mirrors when the hosted sources are unreachable:

```bash
python -m marimo export html-wasm notebook.py -o dist --offline \
  --pyodide-index-url https://mirror.example.com/pyodide/full/ \
  --pypi-index-url https://mirror.example.com/pypi/simple/
```

`--pyodide-index-url` points at a mirror of the Pyodide `full/` distribution
named in `marimo export html-wasm --help`. marimo downloads the runtime, its
`pyodide-lock.json`, and the Pyodide packages the notebook needs from it, and
stops the export when the mirror serves another Pyodide version. Imports resolve
against that lockfile, so declare other imported packages, such as `anywidget`,
in the notebook's inline script metadata.

`--pypi-index-url` points at a package index, such as a PyPI mirror. marimo
resolves each dependency from the Pyodide lockfile first and from this index
otherwise, which also covers private packages hosted there. With
`--pyodide-index-url`, the index provides `marimo-base` for your marimo version,
`black`, and `sqlglot` for SQL notebooks. Alone, `--pypi-index-url` keeps
marimo's hosted lockfile, which downloads marimo's own packages from
`files.pythonhosted.org`, so pass both flags when that host is blocked. The index
must allow anonymous downloads.

marimo downloads from both mirrors in Python, so they need no CORS headers. The
exported HTML loads only the bundled copies.

The export also runs uv to detect local modules. Point uv at the same index, for
example with
[`UV_DEFAULT_INDEX`](https://docs.astral.sh/uv/reference/environment/#uv_default_index).
