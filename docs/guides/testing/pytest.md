# Testing with pytest

## Testing in notebook

By default, marimo discovers and executes tests inside your notebook.
When the optional `pytest` dependency is present, marimo runs `pytest` on cells that
consist exclusively of test code - i.e. functions whose names start with `test_` or
classes whose names start with `Test`. If a cell mixes in anything else (helper
functions, constants, variables, imports, etc.), that cell is skipped by the test
runner (we recommend you move helpers to another cell).

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
