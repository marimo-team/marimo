# Testing

## Directory Structure

- **Snapshots**: Store in `snapshots/` directory next to your test file
- **Fixtures**: Store test input files in `fixtures/` directory next to your test file

```
tests/_convert/ipynb/
├── test_ipynb_converter.py
├── snapshots/          # Expected outputs
└── fixtures/           # Test inputs
```

## Snapshot Testing

```python
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)
snapshot("output.py.txt", result)  # Auto-creates/compares snapshot
```

## Kernel Fixtures

Available in `tests/conftest.py`:

- `k` - Default kernel (autorun, relaxed)
- `strict_kernel` - Strict execution mode
- `lazy_kernel` - Lazy execution mode
- `run_mode_kernel` - RUN mode (not EDIT)
- `mocked_kernel` - Full MockedKernel wrapper
- `executing_kernel` - Execution context installed
- `any_kernel` - Parametrized: runs test 3x (k, strict, lazy)
- `execution_kernel` - Parametrized: runs test 2x (k, strict)

## Running Tests

```bash
uvx hatch run +py=3.12 test:test tests/path/to/test.py
uvx hatch run +py=3.12 test-optional:test tests/path/to/test.py  # with optional deps
```
