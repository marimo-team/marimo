# Image Compare

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    from PIL import Image, ImageDraw

    # A colorful "before" image, compared against its grayscale "after".
    before_image = Image.new("RGB", (600, 400), "white")
    _draw = ImageDraw.Draw(before_image)
    for _x in range(0, 600, 40):
        _draw.rectangle(
            [_x, 0, _x + 20, 400], fill=(_x % 256, (_x * 2) % 256, 128)
        )
    _draw.ellipse([200, 100, 400, 300], fill=(255, 140, 0))
    after_image = before_image.convert("L").convert("RGB")

    mo.image_compare(
        before_image=before_image,
        after_image=after_image,
        value=30,
        direction="horizontal",
    )
    return
```

///

::: marimo.image_compare
