# Python Backend Guidelines

## Testing

Tests live in `tests/` folder, mirroring `marimo/` structure.

```bash
uv run --group test pytest tests/path/to/test.py
uv run --group test-optional pytest tests/path/to/test.py  # with optional deps
uv run --group test --python 3.11 pytest tests/path/to/test.py  # specific python version
```

We should utilize inline-snapshots more often to verify the outputs of objects, functions, etc.
Avoid individual property assertions, opt for full object comparisons.

```python
from inline_snapshot import snapshot
from dirty_equals import IsStr

def test_function():
    assert func() == snapshot({
        "prop1": IsStr(),
        "prop2": "some string",
    })
```

## Code Style

- When writing comments, keep them minimal. Comments should explain "why", not "what"

## Import handling

Generally, we should import at the top of the file. If there are circular imports, it means the file structure is not optimal. Refactor code to remove circular dependencies.

Heavy dependencies must be imported lazily

```python
def get_dataframe():
    import pandas as pd  # altair, duckdb, numpy, polars, pyarrow, sqlglot, etc.
    return pd.DataFrame()
```
