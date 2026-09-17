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
the exported HTML:

```bash
pip install playwright
playwright install chromium
marimo export html-wasm notebook.py -o dist --offline
```

The export requires internet access. Playwright runs Pyodide to resolve
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
[inline script metadata](../package_management/inlining_dependencies.md).
Declare PyPI dependencies in that metadata, including packages installed
dynamically by the notebook.

`--offline` bundles Python dependencies. Data files, remote API calls, and
JavaScript assets fetched by notebook code or widgets still need local
alternatives. Serve the export over HTTP even when using it offline.

Without `--offline`, the browser uses the default hosted Python runtime and
package sources.
