# Self-host WebAssembly notebooks

As an alternative to [GitHub Pages](github_pages.md), it is possible to self-host
exported [WebAssembly notebooks](../wasm.md):

-   [Export to WASM HTML](../exporting.md#export-to-wasm-powered-html).
-   Serve the exported file over HTTP.
-   Serve the assets in the `assets` directory, next to the HTML file.
-   Possibly configure your web server to support serving `application/wasm/`
    files with the correct headers.
