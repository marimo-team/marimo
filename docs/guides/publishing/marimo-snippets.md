# Publish using `marimo-snippets` 

You can host marimo entire notebooks directly by exporting them to WASM but thanks to the `marimo-snippets` library you can also choose to embed a marimo notebook on your site via markdown blocks. 

Here's a quick demo on how you might set that up. 

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

!!! note

    You might wonder why we wrap the `<marimo-button>` element with an extra `<div>`. This is related to how different markdown preprocessors might handle the custom HTML elements. To guarantee that this approach works across most markdown tools, we need to wrap the custom elements in a block element.

This will embed an iframe on your behalf with an interactive slider. 

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

Check the [Github repository](https://github.com/marimo-team/marimo-snippets) to learn more about [the configuration options](https://github.com/marimo-team/marimo-snippets?tab=readme-ov-file#configuration).