# Video

{{ create_marimo_embed("""

```python
@app.cell
def __():
    mo.video(
        src="https://v3.cdnpk.net/videvo_files/video/free/2013-08/large_watermarked/hd0992_preview.mp4",
        controls=False,
    )
    return
```

""", size="medium") }}

::: marimo.video
