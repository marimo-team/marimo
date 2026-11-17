Areas where marimo bugs tend to hide:

- **Reactivity.** Changes to `marimo/_ast` or `marimo/_runtime/dataflow` can alter which cells run, in what order, or which definitions a cell is considered to own. Check the effect on stale-cell handling and on deleting or renaming variables.
- **Notebook files.** Notebooks are Python files written by `marimo/_ast/codegen.py` and read by `marimo/_ast/parse.py` and `load.py`. Existing notebooks must keep loading, and a save followed by a load must preserve the notebook.
- **Frontend and backend contract.** Messages and endpoints are described in `packages/openapi/api.yaml`. Check that backend changes to request or response models are reflected there and in the frontend, and that older frontends or kernels fail gracefully.
- **Server security.** Endpoints under `marimo/_server/api/endpoints` can be reached by anyone with the server URL and token. Look for missing authentication, file access outside the notebook directory, and code execution in read-only or run mode.
- **WebAssembly.** Code under `marimo/_runtime/_wasm` and `marimo/_pyodide` runs in the browser, where threads, subprocesses, and most of the filesystem are unavailable.
