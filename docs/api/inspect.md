# Inspect

Use `mo.inspect()` to explore Python objects with a rich, interactive display of their attributes, methods, and documentation.

## Example

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