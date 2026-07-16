# Testing with pytest

## Testing in notebook

By default, marimo discovers and executes tests inside your notebook.
When the optional `pytest` dependency is present, marimo runs `pytest` on cells that
consist exclusively of test code - i.e. functions whose names start with `test_`,
classes whose names start with `Test`, or functions decorated with `@pytest.fixture`.
If a cell mixes in anything else (helper functions, constants, variables, imports, etc.),
that cell is skipped by the test runner (we recommend you move helpers to another cell).

For example,

/// marimo-embed

```python
@app.cell
def __():
    import pytest
    def inc(x):
        return x + 1
    return inc, pytest

@app.cell
def __(inc, pytest):
    class TestBlock:
        @staticmethod
        def test_fails():
            assert inc(3) == 5, "This test fails"

        @staticmethod
        def test_sanity():
            assert inc(3) == 4, "This test passes"

    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_parameterized(x, y):
        assert inc(x) == y
    return
```

///

!!! note "Reactive tests can be disabled"

    You can disable this behavior with the `runtime.reactive_test` option in the
    configuration file.

## Testing at the command-line

Since marimo notebooks are Python programs, you can test them using
[`pytest`](https://docs.pytest.org/en/stable/), a popular testing framework
for Python.

For example,

```bash
pytest test_notebook.py
```

runs and tests all notebook cells whose names start with `test_`, or cells that
contain only `test_` functions and `Test` classes (just like in notebook tests).

!!! tip "Naming cells"

    Name a cell by giving its function a name in the notebook file, or using
    the cell action menu in the notebook editor.

!!! note "Use marimo notebooks just like normal pytest tests"

    Include test notebooks (notebooks whose names start with `test_`) in your
    standard test suite, and `pytest` will discover them automatically.
    In addition, you can write self-contained notebooks that contain their own
    unit tests, and run `pytest` on them directly (`pytest my_notebook.py`).

## Example

Running `pytest` on

```python
# content of test_notebook.py
import marimo

__generated_with = "0.10.6"
app = marimo.App()


@app.cell
def _():
    def inc(x):
        return x + 1
    return (inc,)


@app.cell
def test_fails(inc):
    assert inc(3) == 5, "This test fails"


@app.cell
def test_sanity(inc):
    assert inc(3) == 4, "This test passes"

@app.cell
def collection_of_tests(inc, pytest):
    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_answer(x, y):
        assert inc(x) == y, "These tests should pass."

@app.cell
def imports():
    import pytest
    return pytest
```

prints

```pytest
============================= test session starts ==============================
platform linux -- Python 3.12.9, pytest-8.3.5, pluggy-1.5.0
rootdir: /notebooks
configfile: pyproject.toml
collected 4 items

test_notebook.py::test_fails FAILED                                       [ 25%]
test_notebook.py::test_sanity PASSED                                      [ 50%]
test_notebook.py::MarimoTestBlock_0::test_parameterized[3-4] PASSED       [ 75%]
test_notebook.py::MarimoTestBlock_0::test_parameterized[4-5] PASSED       [100%]

=================================== FAILURES ===================================
__________________________________ test_fails __________________________________

    # content of test_notebook.py
    import marimo

    __generated_with = "0.10.6"
    app = marimo.App()


    @app.cell
    def _():
        def inc(x):
            return x + 1
        return (inc,)


    @app.cell
    def test_fails(inc):
>       assert inc(3) == 5, "This test fails"
E       AssertionError: This test fails
E       assert 4 == 5
E        +  where 4 = <function inc>(3)

test_notebook.py:17: AssertionError
=========================== short test summary info ============================
FAILED test_notebook.py::test_fails - AssertionError: This test fails
========================= 1 failed, 3 passed in 0.82s ==========================
```

## Using Pytest Fixtures

marimo notebooks can define pytest fixtures, but **fixture resolution does not follow
the same rules as ordinary notebooks cells**. The reliable pattern is to define
fixtures **in the same cell as the tests that use them**.

### Recommended: fixture and test in the same cell

```python
@app.cell
def _():
    import pytest
    return pytest


@app.cell
def _(pytest):
    @pytest.fixture
    def temp_file():
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            yield f

    def test_writes_to_file(temp_file):
        temp_file.write(b"hello")
        temp_file.seek(0)
        assert temp_file.read() == b"hello"
```

This works because pytest's static collector sees both the `@pytest.fixture` and the
test function in the same nested scope in the exported notebook module.

### Class fixtures (same cell)

Class-scoped fixtures also work when the fixture methods and tests live on the same
class in one cell:

```python
@app.cell
def _():
    import pytest
    return pytest


@app.cell
def _(pytest):
    class TestDatabase:
        @pytest.fixture(scope="class")
        def connection(self):
            return create_connection()

        def test_query(self, connection):
            result = connection.query("SELECT 1")
            assert result == 1
```

### Shared helpers: plain Python modules

For shared setup, put pure helper functions (not pytest fixtures) in a normal `.py`
module and call them from each test:

```python
# helpers.py
def sample_data():
    return [1, 2, 3]


# test_notebook.py
@app.cell
def _():
    from helpers import sample_data

    def test_data_loaded():
        assert len(sample_data()) > 0
```

If you truly need **pytest fixtures**, keep defining `@pytest.fixture` next to the
tests in the same cell (or in `conftest.py` *and* wire parameters carefully — see
limitations below).

### Patterns that usually fail

!!! warning "Do not rely on these as "supported""

    - **Importing fixtures in `app.setup` and listing them as cell refs.** Setup may
      import the fixture *function*, but pytest still expects fixture *injection*.
      Tests often receive a `FixtureFunctionDefinition` (or similar) instead of the
      resolved value.
    - **`conftest.py` fixtures without local parameters.** Even when pytest discovers
      a fixture from `conftest.py`, marimo cell signatures still need names that the
      notebook graph can provide. Tests that only list the fixture as a pytest
      parameter can raise `NameError` at cell-definition time if that name is not a
      cell reference. Prefer same-cell fixtures or plain helpers.

### Why fixtures are special

!!! info "Fixture Limitations"

    Fixtures defined in one cell **cannot** be used by tests in a different cell.
    Pytest collects tests **statically** by parsing the notebook file without
    executing marimo's runtime graph. During collection it can see fixtures defined
    in the same scope as the test (and module-level fixtures in pure Python files),
    but it cannot reconstruct fixtures that would only exist after other cells run.

    Running the entire notebook solely for fixture discovery would be expensive, and
    static analysis cannot know which fixture names become available after marimo
    topological execution.
