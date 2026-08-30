# WebAssembly HTML

Export your notebook to a self-contained HTML file that runs using [WebAssembly](../wasm.md).

/// tip | Easiest way to share interactive notebooks
For the simplest way to share interactive notebooks online, including WebAssembly notebooks, use [molab](../molab.md).
///

```bash
# export as readonly, with code locked
marimo export html-wasm notebook.py -o output_dir --mode run
# export as an editable notebook
marimo export html-wasm notebook.py -o output_dir --mode edit
```

In `--mode run`, a notebook configured with the slides layout opens as a
reveal.js deck. The export preserves slide structure, speaker notes, and deck
settings while Pyodide keeps notebook controls reactive.
Speaker notes are embedded in the HTML file and readable by anyone who
receives it.

Use static HTML when the presentation needs reveal.js speaker view. A
WebAssembly HTML deck keeps one Pyodide runtime in the presentation window.

The exported HTML file will run your notebook using WebAssembly, making it completely self-contained and executable in the browser. This means users can interact with your notebook without needing Python or marimo installed.

Options:

- `--mode`: Choose between `run` (read-only) or `edit` (allows editing)
- `--output`: Directory to save the HTML and required assets
- `--show-code/--no-show-code`: Whether to initially show or hide the code in the notebook
- `--watch/--no-watch`: Watch the notebook for changes and automatically export
- `--include-cloudflare`: Write configuration files necessary for deploying to Cloudflare
- `--execute/--no-execute`: Run the notebook before exporting and embed its outputs as a preview. Where possible, this uses an isolated environment pinned to WASM-compatible packages

Note that WebAssembly notebooks have [limitations](../wasm.md#limitations); in particular,
[many but not all packages work](../wasm.md#packages). If your notebook runs both
locally and in the browser, use [PEP 508 environment
markers](../wasm.md#platform-specific-dependencies-pep-508) in script metadata to
exclude native-only dependencies from WASM installs.

Run `marimo check notebook.py --select MW` before exporting to catch WASM
incompatibilities early:

- [MW001](../lint_rules/rules/incompatible_import.md): an incompatible import
- [MW002](../lint_rules/rules/unsafe_system_call.md): an unsafe system call
- [MW003](../lint_rules/rules/incompatible_package.md): a dependency without a WASM-compatible wheel

!!! note "Note"

    The exported file must be served over HTTP to function correctly - it
    cannot be opened directly from the filesystem (`file://`). Your server must
    also serve the assets in the `assets` directory, next to the HTML file. For
    a simpler publishing experience, use [molab](../molab.md), publish to [GitHub
    Pages](../publishing/github.md#publish-to-github-pages), [Cloudflare](../publishing/cloudflare.md), or
    [self-host](../publishing/self_host_wasm.md).

??? note "Deploying to Cloudflare"

    You can include `--include-cloudflare` for deploying to Cloudflare. For example:

    ```
    marimo export html-wasm notebook.py -o my_app/dist --include-cloudflare
    ```

    To run locally, run:

    ```
    npx wrangler dev
    ```

    To deploy to Cloudflare, run:

    ```
    npx wrangler deploy
    ```

## Exporting with cached execution { #exporting-with-cached-execution }

With caching, you can publish WebAssembly notebooks whose cells are expensive
or cannot run in the browser (a small `torch` training run, for example). If your
notebook has [automatic cell
caching](../../api/caching.md#automatic-cell-caching) enabled, `--execute` runs
the notebook once and bundles the resulting cell cache into the export. When the
exported notebook loads, each cached cell hydrates from that bundle instead of
recomputing in WebAssembly. The rest of the notebook stays fully live and
interactive.

Bundling a cache needs both the runtime setting and the `--execute` flag:

```toml title="pyproject.toml"
[tool.marimo.runtime]
cache_cells = true
```

```bash
marimo export html-wasm notebook.py -o output_dir --execute
```

marimo copies the cached entries into a `public/cache/` directory alongside the
export. At load time, the browser runtime fetches them over HTTP instead of
recomputing the corresponding cells.

### Cached values from packages WebAssembly cannot install { #native-only-objects }

A cached cell can define a top-level value from a package that WebAssembly
cannot install, like a `torch.nn.Module`. You do not need to keep such values
out of the cache. When the exported notebook cannot correctly restore
variables from cache, marimo binds the variable to a stub instead of raising
an error. The notebook will load normally and behave normally as the
evaluation of the stubbed variable is deferred until an attempt to use it.

When an incompatible variable load is triggered, marimo will attempt to
recompute its definition from the notebook, which in turn may fail if the
behavior is not compatible with the WebAssembly environment.

For instance, if the browser does not have a package a new cell needs, the rerun fails:

```python
# /// script
# dependencies = [
#     "marimo",
#     "torch; sys_platform != 'emscripten'",  # native-only; excluded from WASM
# ]
#
# [tool.marimo.runtime]
# cache_cells = true
# ///

# --- Cell 1 ---

import torch # load deferred; torch is not available in the browser
import numpy as np

# --- Cell 2 --- # Cell 2 is cached and skipped
model = torch.nn.Linear(4, 2)
# ... train the model ...

# --- Cell 3 --- # Cell 3 is cached and skipped
x = np.array(model(torch.rand(1, 4)))
x # Output is initially visible!

# --- Cell 4 --- # If this is a new cell it'll still work! `x` is loaded from cache.
x + x # numpy values can be used in the browser, so this works fine

# --- Cell 5 --- # If this is a new cell, this will fail
np.array(model(torch.rand(1, 4)))
```

In the exported notebook, `model` hydrates as a stub. Displaying outputs or
referencing the variable in other cached cells still works. Calling `model(...)`
in the new Cell 5 reruns this cell live. That rerun needs `torch`, which is
unavailable in the browser, so it fails there.

To run inference on such a model in the browser, cache a portable form of it
instead of calling the stub. [`moutils.onnx.OnnxRuntime`](https://github.com/marimo-team/moutils#onnx-runtime-adapter)
does this for PyTorch and JAX models: it exports the model to ONNX, and the
runtime it returns is itself cacheable. In the browser, that runtime runs
inference with `onnxruntime-web` instead of the original framework.

!!! note "This is a point-in-time snapshot"

    Cache bundling covers only the cells whose cache is valid at export time.
    Editing a cell, or changing an input it depends on, invalidates that
    cell's cache. Then the browser must run the cell's real code instead of
    hydrating it from the bundle. If that code needs a package WebAssembly
    cannot install (like `torch`), the cell reports an error. After such a
    change, re-run and re-export the notebook.

### Caching precomputed values { #precomputed-values }

An alternative to caching for runtime evaluation is precomputing every
possible output of a cell and bundling them into the export. This is useful for
notebooks that have a small, known set of states, such as those with dropdowns
or sliders that index into a fixed list of options. By precomputing every
reachable output ahead of time, you can avoid waiting for the cache to warm up
during use.

The pattern has four parts:

1. Expose UI elements as indices into fixed option lists of plain, hashable
   values (strings, numbers) — not the objects or callables the indices
   select. UI-defining cells always rerun live on load, even on a cache hit,
   so keep them free of anything that touches an unavailable package.
2. Pull the expensive computation into a plain function keyed on those indices,
   decorated with `@mo.persistent_cache(method="lazy")`. Use `method="lazy"`:
   `method="pickle"` does not bundle well for the WASM export.
3. Add a cell that calls that function for every combination of indices,
   guarded to run only outside the browser, for example with
   `sys.platform != "emscripten"`.
4. Return WASM-native values (numbers, `numpy` arrays, strings) from the
   cached function, so cells that use the result work directly in the
   browser.

```python
# /// script
# dependencies = [
#     "marimo",
#     "torch; sys_platform != 'emscripten'",  # native-only; excluded from WASM
# ]
#
# [tool.marimo.runtime]
# cache_cells = true
# ///

# --- Cell 1 --- # setup; not UI-defining, so a cache hit can skip it entirely
import sys
import torch
import marimo as mo

FN_LABELS = ["x^2", "sin(x)"]

# --- Cell 2 --- # UI-defining cells always rerun live on load, so keep them
# to plain, hashable literals like FN_LABELS above
fn = mo.ui.dropdown(
    options={label: i for i, label in enumerate(FN_LABELS)}, value="x^2"
)
fn

# --- Cell 3 --- # the expensive part, keyed on the dropdown's index
@mo.persistent_cache(method="lazy")
def compute(fn_idx):
    x = torch.linspace(-1, 1, 100)
    y = x**2 if fn_idx == 0 else torch.sin(x)
    return {"label": FN_LABELS[fn_idx], "x": x.numpy(), "y": y.numpy()}

# --- Cell 4 ---
result = compute(fn.value)
result

# --- Cell 5 --- # warm the cache for every dropdown option before exporting
if sys.platform != "emscripten":
    for _fn_idx in range(len(FN_LABELS)):
        compute(_fn_idx)
```

Export with `marimo export html-wasm notebook.py -o output_dir --execute`.
The precompute cell runs during that server-side pass and populates one
cache entry per dropdown option. All of them get bundled into
`public/cache/`. In the browser, every dropdown selection is already
cached, so switching between options never triggers a live rerun.

## Including local modules and wheels

`marimo export html-wasm` includes Python modules imported by your notebook
when they resolve to local files. For example, if `notebook.py` imports `foo`
and `foo.py` lives in the same directory, marimo builds a pure-Python wheel for
`foo.py`, copies it to `public/wheels` in the export directory, and installs
the wheel when the notebook starts in the browser.

```text
notebooks/
|-- notebook.py
`-- foo.py
```

```python title="notebooks/notebook.py"
import foo
```

```bash
marimo export html-wasm notebooks/notebook.py -o output_dir
```

Package imports keep their package layout. A local `foo.py` is written into the
wheel as top-level `foo.py`, while a local package such as `helpers/__init__.py`
stays under `helpers/`. If a local module imports another local module, the
imported file is included in the export too.

Local module resolution requires [`uv`](https://docs.astral.sh/uv/). Install it
with `pip install "marimo[sandbox]"` or use the
[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

For local modules outside the notebook directory, configure
[`pythonpath`](../configuration/runtime_configuration.md#python-path) so marimo
can resolve the import.

If you already build a local wheel, reference it from the notebook's
[inline script metadata](../package_management/inlining_dependencies.md):

```python
# /// script
# dependencies = ["my-package"]
# [tool.uv.sources]
# my-package = { path = "dist/my_package-0.1.0-py3-none-any.whl" }
# ///
```

During export, marimo copies the referenced wheel to `public/wheels` and
rewrites the browser metadata to install that hosted wheel URL.

Local modules and wheels run in Pyodide at browser startup. Imported
third-party packages must be available in Pyodide or installable from a
WASM-compatible wheel.

## Testing the export

You can test the export by running the following command in the directory containing your notebook:

```bash
cd path/to/output_dir
python -m http.server
```

## Including data files

See the docs for [mo.notebook_location][marimo.notebook_location] to learn how
to include data files in exported WASM HTML notebooks.

## Exporting multiple notebooks

In order to export multiple notebooks under the same folder, you can use the following snippet:

```bash
files=("batch_and_form.py" "data_explorer.py")

for file in "${files[@]}"; do
  without_extension="${file%.*}"
  marimo export html-wasm "$file" -o site/"$without_extension".html --mode run
done
```

Optionally, you can create an `index.html` file in the public directory:

```bash
echo "<html><body><ul>" > site/index.html
for file in "${files[@]}"; do
  without_extension="${file%.*}"
  echo "<li><a href=\"$without_extension.html\">$without_extension</a></li>" >> site/index.html
done
echo "</ul></body></html>" >> site/index.html
```

## Embed marimo outputs in HTML using Islands

!!! note "Preview"

    Islands are an early feature. While the API likely won't change, there are some improvements we'd like to make before we consider them stable.
    Please let us know on [GitHub](https://github.com/marimo-team/marimo/issues) if you run into any issues or have any feedback!

marimo islands are a way to embed marimo outputs and/or python code in your HTML that will become interactive when the page is loaded. This is useful for creating interactive blog posts, tutorials, and educational materials, all powered by marimo's reactive runtime.

Check out an [example island-powered document](../island_example.md).

### Generating islands

Use `MarimoIslandGenerator` to generate HTML for islands

!!! example
    /// tab | From code blocks

    ```python
    import asyncio
    import sys
    from marimo import MarimoIslandGenerator

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def main():
        generator = MarimoIslandGenerator()
        block1 = generator.add_code("import marimo as mo")
        block2 = generator.add_code("mo.md('Hello, islands!')")

        # Build the app
        app = await generator.build()

        # Render the app
        output = f"""
        <html>
            <head>
                {generator.render_head()}
            </head>
            <body>
                {block1.render(display_output=False)}
                {block2.render()}
            </body>
        </html>
        """
        print(output)
        # Save the HTML to a file
        output_file = "output.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)

    if __name__ == '__main__':
        asyncio.run(main())
    ```

    ///

    /// tab | From notebook files

    ```python
    from marimo import MarimoIslandGenerator

    # Create the generator from file
    generator = MarimoIslandGenerator.from_file("./<notebook-name>.py", display_code=False)

    # Generate and print the HTML without building
    # This will still work for basic rendering, though without running the cells
    html = generator.render_html(include_init_island=False)
    print(html)
    # Save the HTML to a file
    output_file = "output.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    ```

    ///

Any relevant `.html` that gets generated can be run through the [`development.md`](https://github.com/marimo-team/marimo/blob/main/frontend/islands/development.md) file instructions.

### Island payloads

`MarimoIslandGenerator.render_html(include_payload=True)` and `render_body(include_payload=True)` include a JSON payload. The payload stores each cell's code, rendered output HTML, output MIME type, and display settings.

The islands runtime uses this payload to hydrate the page. The DOM still provides the visible island slots, and the payload provides the runtime cell code and output metadata.

An emitted payload looks like this. HTML-sensitive characters inside JSON strings are escaped before marimo writes the script tag.

```html
<script type="application/vnd.marimo.islands+json">{"schemaVersion":1,"appId":"main","cells":[{"cellId":"cell-1","code":"mo.md('Hello, islands!')","outputHtml":"\u003cspan\u003eHello, islands!\u003c/span\u003e","outputMimetype":"text/markdown","reactive":true,"displayCode":false,"displayOutput":true}]}</script>
```

If you post-process island HTML, preserve the script tag with type `application/vnd.marimo.islands+json` and keep its contents unchanged.

### Islands in action

!!! warning "Advanced topic!"

    Islands are an advanced concept that is meant to be a building block for creating integrations with existing tools such as static site generators or documentation tools.

In order to use marimo islands, you need to import the necessary JS/CSS headers in your HTML file, and use our custom HTML tags to define the islands.

```html
<head>
  <!-- marimo js/ccs --
  <script type="module" src="https://cdn.jsdelivr.net/npm/@marimo-team/islands@<version>/dist/main.js"></script>
  <link
    href="https://cdn.jsdelivr.net/npm/@marimo-team/islands@<version>/dist/style.css"
    rel="stylesheet"
    crossorigin="anonymous"
  />
  <!-- fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;500;700&amp;family=Lora&amp;family=PT+Sans:wght@400;700&amp;display=swap"
    rel="stylesheet"
  />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css"
    integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
    crossorigin="anonymous"
  />
</head>

<body>
  <marimo-island data-app-id="main" data-cell-id="MJUe" data-reactive="true">
    <marimo-cell-output>
      <span class="markdown">
        <span class="paragraph">Hello, islands!</span>
      </span>
    </marimo-cell-output>
    <marimo-cell-code hidden>mo.md('Hello islands 🏝️!')</marimo-cell-code>
  </marimo-island>
</body>
```

::: marimo.MarimoIslandGenerator
