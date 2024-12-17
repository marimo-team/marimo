# Diagrams

{{ create_marimo_embed("""

```python
@app.cell
def __():
    mo.mermaid("graph TD\n  A[Christmas] -->|Get money| B(Go shopping)\n  B --> C{Let me think}\n  C -->|One| D[Laptop]\n  C -->|Two| E[iPhone]\n  C -->|Three| F[Car]")
    return
```

""", size="medium") }}

## Mermaid diagrams

::: marimo.mermaid
