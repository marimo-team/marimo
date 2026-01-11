# Python Backend Guidelines

You are an expert in Python, websockets protocol, and Starlette/ASGI web frameworks.

## Key Principles

- Prioritize readability and maintainability; follow PEP 8 (79 char line limit)
- Use type hints consistently throughout the codebase
- Use descriptive variable and function names (lowercase with underscores)
- Use `Final` for constants: `_name: Final[str] = "marimo-tabs"`
- Private modules use `_` prefix (e.g., `_plugins`, `_server`, `_utils`)

## Type Hints

- Always add return type annotations to functions
- Use modern typing syntax (`list[str]` not `List[str]`, `str | None` not `Optional[str]`)

## Error Handling

- Raise specific exceptions, never bare `raise Exception`
- Use `HTTPException` with appropriate status codes for API errors:

```python
from marimo._utils.http import HTTPStatus
raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="AI is not configured.")
```

## Logging

```python
from marimo import _loggers
LOGGER = _loggers.marimo_logger()

LOGGER.debug("Diagnostic info: %s", value)      # troubleshooting
LOGGER.info("Standard operation: %s", value)    # normal events
LOGGER.warning("Unexpected but handled: %s", value)  # recoverable issues
LOGGER.error("Functionality broken: %s", value) # critical errors
```

Use `%s` formatting (not f-strings) for lazy evaluation. Never log sensitive data.

## Dataclasses vs msgspec

Use **msgspec.Struct** for API models (everything in `_server/models/`), commands, and fast JSON serialization:

```python
import msgspec

class SaveNotebookRequest(msgspec.Struct, rename="camel"):
    cell_ids: list[CellId_t]
    codes: list[str]
    filename: str
    persist: bool = True
```

Use **dataclasses** for internal structures, test fixtures, and complex initialization.

## Lazy Imports

Heavy dependencies must be imported lazily (banned at module level by ruff):

```python
def get_dataframe():
    import pandas as pd  # altair, duckdb, numpy, polars, pyarrow, sqlglot, etc.
    return pd.DataFrame()
```

## Testing

Tests live in `tests/` folder, mirroring `marimo/` structure.

```bash
uvx hatch run +py=3.12 test:test tests/path/to/test.py
uvx hatch run +py=3.12 test-optional:test tests/path/to/test.py  # with optional deps
```

### Best Practices

```python
# Focus on single use-case per test
def test_number_init() -> None:
    number = ui.number(1, 10)
    assert number.start == 1 and number.stop == 10

# Test error cases with context managers
def test_number_out_of_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.number(1, 10, value=11)
    assert "must be less than or equal" in str(e.value)

# Skip when dependencies missing
HAS_PANDAS = DependencyManager.pandas.has()

@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_with_pandas() -> None:
    import pandas as pd
```

- pytest-asyncio configured globally (no `@pytest.mark.asyncio` needed)
- Test timeout: 30 seconds
- Validate entire object state, not individual attributes (e.g. `assert obj == expected` instead of `assert obj.attr == expected.attr`)

### Fixtures and Snapshots

```python
# Use fixtures from conftest.py
@pytest.fixture
def k() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    yield mocked.k
    mocked.teardown()

# Snapshot testing for complex outputs
from tests.mocks import snapshotter
snapshot = snapshotter(__file__)
snapshot(filename, output)
```

### Debugging

Read error messages and test code first. Add debug prints if root cause unclear.

## Code Style

- Google-style docstrings
- Explicit encoding in `open()`
- Typecheck and lint with `make py-check`
- Use `log_never` to ensure exhaustive handling
- Comments explain "why", not "what" - keep minimal
