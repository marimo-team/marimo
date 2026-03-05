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

The exported HTML file will run your notebook using WebAssembly, making it completely self-contained and executable in the browser. This means users can interact with your notebook without needing Python or marimo installed.

Options:

- `--mode`: Choose between `run` (read-only) or `edit` (allows editing)
- `--output`: Directory to save the HTML and required assets
- `--show-code/--no-show-code`: Whether to initially show or hide the code in the notebook
- `--watch/--no-watch`: Watch the notebook for changes and automatically export
- `--include-cloudflare`: Write configuration files necessary for deploying to Cloudflare

Note that WebAssembly notebooks have [limitations](../wasm.md#limitations); in particular,
[many but not all packages work](../wasm.md#packages).

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
