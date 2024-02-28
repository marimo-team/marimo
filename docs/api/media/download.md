# Download Media

```{eval-rst}
.. marimo-embed::
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

```{eval-rst}
.. autofunction:: marimo.download
```
