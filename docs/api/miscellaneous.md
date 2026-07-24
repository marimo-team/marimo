# Miscellaneous

::: marimo.running_in_notebook

::: marimo.defs

::: marimo.refs

::: marimo.notebook_dir

::: marimo.notebook_location

## Inspect

Use `mo.inspect()` to explore Python objects with a rich, interactive display of their attributes, methods, and documentation.

### Example

```python
import marimo as mo

# Inspect a class
mo.inspect(list, methods=True)

# Inspect an instance
my_dict = {"key": "value"}
mo.inspect(my_dict)

# Show all attributes including private and dunder
mo.inspect(my_dict, all=True)
```

::: marimo.inspect

## Serving notebooks (ASGI)

Use [`marimo.create_asgi_app`](create_asgi_app.md) to embed run-mode notebooks in an ASGI application.
