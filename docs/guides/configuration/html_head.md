# Custom HTML Head

You can include a custom HTML head file to add additional functionality to your notebook, such as analytics, custom fonts, meta tags, or external scripts. The contents of this file will be injected into the `<head>` section of your notebook.

To include a custom HTML head file, specify the relative file path in your app configuration. This can be done through the marimo editor UI in the notebook settings (top-right corner).

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

4. **External Scripts and Libraries**

```html
<!-- head.html -->
<!-- Load external JavaScript libraries -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>

<!-- Load external CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
```
