# Running unit tests with pytest

Since marimo notebooks are Python programs, you can test them using
[`pytest`](https://docs.pytest.org/en/stable/), a popular testing framework
for Python.



For example,

```bash
pytest test_notebook.py
```

runs and tests all notebook cells whose names start with `test_`.

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
    return inc


@app.cell
def test_answer(inc):
    assert inc(3) == 5, "This test fails"


@app.cell
def test_sanity(inc):
    assert inc(3) == 4, "This test passes"
```

prints

```pytest
============================= test session starts ==============================
platform linux -- Python 3.11.10, pytest-8.3.3, pluggy-1.5.0
rootdir: /notebooks
configfile: pyproject.toml
collected 2 items

test_notebook.py F.                                                       [100%]

=================================== FAILURES ===================================
__________________________________ test_fails __________________________________

    import marimo

    __generated_with = "0.10.6"
    app = marimo.App(width="medium")


    @app.cell
    def _():
        def inc(x):
            return x + 1
        return (inc,)


    @app.cell
    def test_answser(inc):
>       assert inc(3) == 5, "This test fails"
E       AssertionError: This test fails

test_notebook.py:16: AssertionError
=========================== short test summary info ============================
FAILED test_notebook.py::test_fails - AssertionError: This test fails
========================= 1 failed, 1 passed in 0.20s ===========================
```
