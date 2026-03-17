# Self-host WebAssembly notebooks

As an alternative to [GitHub Pages](github.md#publish-to-github-pages), it is possible to self-host
exported [WebAssembly notebooks](../wasm.md):

-   [Export to WASM HTML](../exporting/webassembly_html.md).
-   Serve the exported file over HTTP.
-   Serve the assets in the `assets` directory, next to the HTML file.
-   Possibly configure your web server to support serving `application/wasm/`
    files with the correct headers.
