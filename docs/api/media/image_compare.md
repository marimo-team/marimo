# Image Compare

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    before_image = "https://picsum.photos/200/301.jpg"
    after_image = "https://picsum.photos/200/300.jpg"
    
    mo.image_compare(
        before_image=before_image,
        after_image=after_image,
        value=30,
        direction="horizontal"
    )
    return
```

///

::: marimo.image_compare
