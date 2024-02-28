# Diagrams

```{eval-rst}
.. marimo-embed::
    :size: medium

    @app.cell
    def __():
        mo.mermaid("graph TD\n  A[Christmas] -->|Get money| B(Go shopping)\n  B --> C{Let me think}\n  C -->|One| D[Laptop]\n  C -->|Two| E[iPhone]\n  C -->|Three| F[Car]")
        return
```

## Mermaid diagrams

```{eval-rst}
.. autofunction:: marimo.mermaid
```

## Statistic cards

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        mo.hstack([
            mo.stat(value="100.54", label="Open price", caption="2.4", direction="increase", bordered=True),
            mo.stat(value="100.54", label="Close price", caption="2.4", direction="decrease", bordered=True),
        ])
        return
```

```{eval-rst}
.. autofunction:: marimo.stat
```
