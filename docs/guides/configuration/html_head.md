# Custom HTML Head

You can include a custom HTML head file to add additional functionality to your notebook, such as analytics, custom fonts, meta tags, or external scripts. The contents of this file will be injected into the `<head>` section of your notebook.

!!! warning "Run mode only"

    Custom HTML head content is **only** injected in **run mode** (`marimo run`, including apps exported or served as run experiences). It is **not** applied in **edit mode** (`marimo edit`), which deliberately blocks `html_head_file` because the file may contain arbitrary scripts.

    If you need custom styling while editing, use [`css_file`](theming.md) instead.

To include a custom HTML head file, specify the relative file path (relative to the notebook file) in your app configuration. This can be done through the marimo editor UI in the notebook settings (top-right corner).

This will be reflected in your notebook file:

```python
app = marimo.App(html_head_file="head.html")
```

## Example Use Cases

Here are some common use cases for custom HTML head content:

1. **Google Analytics**

```html
<!-- head.html -->
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag() {
    dataLayer.push(arguments);
  }
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

2. **Custom Fonts**

```html
<!-- head.html -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet" />
```

3. **Meta Tags**

```html
<!-- head.html -->
<meta name="description" content="My marimo notebook" />
<meta name="keywords" content="data science, visualization, python" />
<meta name="author" content="Your Name" />
<meta property="og:title" content="My Notebook" />
<meta property="og:description" content="Interactive data analysis with marimo" />
<meta property="og:image" content="https://example.com/thumbnail.jpg" />
```

!!! tip "OpenGraph previews"

    For common OpenGraph fields (title, description, image), you can also use notebook OpenGraph metadata in script metadata. See [OpenGraph previews](../publishing/opengraph.md).

4. **External Scripts and Libraries**

```html
<!-- head.html -->
<!-- Load external JavaScript libraries -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>

<!-- Load external CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
```

## Troubleshooting

If your custom head content (a script tag, font, or meta tag) never appears in the running app, work through the following checks.

1. **Confirm you are in run mode.** From the notebook directory run:

   ```bash
   marimo run your_notebook.py
   ```

   Opening the same notebook with `marimo edit` will not inject `html_head_file`.

2. **Path.** `html_head_file` is resolved relative to the notebook path. A bare `head.html` must sit next to the `.py` notebook (or use an explicit relative path).

3. **Reload after edits.** Change the head file, then hard-reload the run-mode tab (or restart `marimo run`) so the template is rebuilt.

4. **Verify.** A minimal head file:

   ```html
   <script>console.log("marimo html head injected")</script>
   ```

   should log once when the run-mode app first loads.
