# Carousel

{{ create_marimo_embed("""

```python
@app.cell
def __():
    mo.carousel([
        mo.md("# Introduction"),
        "By the marimo team",
        mo.md("## What is marimo?"),
        mo.md("![marimo moss ball](https://marimo.io/logo.png)"),
        mo.md("## Questions?"),
    ])
    return
```

""", size="large") }}

::: marimo.carousel
