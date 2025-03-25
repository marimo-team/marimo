# Publish using `marimo-snippets` 

`marimo-snippets` is a single-file JavaScript utility that lets you embed interactive
marimo notebooks in static web pages, powered by WebAssembly. Simply wrap code
elements in a custom tag, and marimo snippets does the rest; marimo-snippets
is even compatible with MkDocs-generated markdown.

Here's a demo:

````md
<div>
<marimo-iframe>
```python
import marimo as mo
```
```python
slider = mo.ui.slider(1, 10)
slider
```

```python
slider.value * "🍃"
```
</marimo-iframe>
</div>

<script src="https://cdn.jsdelivr.net/npm/@marimo-team/marimo-snippets@1"></script>
````

This embeds an iframe on your page with an interactive slider, like the one below.
Fun fact: this page is itself using `marimo-snippets`!

<div>
<marimo-iframe>
```python
import marimo as mo
```
```python
slider = mo.ui.slider(1, 10)
slider
```

```python
slider.value * "🍃"
```
</marimo-iframe>
</div>

<script src="https://cdn.jsdelivr.net/npm/@marimo-team/marimo-snippets@1"></script>

## Configuration 

To configure the rendering behavior globally, you can include script elements *before* the marimo snippets script.

```html
<!-- Optionally configure how buttons and iframes are rendered. -->
<!-- Configuration must come _before_ the main extractor script is loaded. -->
<script type="text/x-marimo-snippets-config">
configureMarimoButtons({title: "Open in a marimo notebook"});
configureMarimoIframes({height: "400px"});
</script>

<script src="https://cdn.jsdelivr.net/npm/@marimo-team/marimo-snippets@1"></script>
```

You can also configure data attributes per-element. 

```html
<marimo-iframe data-height="600px" data-show-code="false">
...
</marimo-iframe>
```

See the [GitHub repository](https://github.com/marimo-team/marimo-snippets) for a full example and [documentation on configuration](https://github.com/marimo-team/marimo-snippets?tab=readme-ov-file#configuration).
