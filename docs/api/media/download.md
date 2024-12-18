# Download Media

/// marimo-embed

```python
@app.cell
def __():
    download_txt = mo.download(
        data="Hello, world!".encode("utf-8"),
        filename="hello.txt",
        mimetype="text/plain",
    )
    download_txt
    return
```

///

::: marimo.download
