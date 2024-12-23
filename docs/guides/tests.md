# Running unit tests with pytest

Since marimo notebooks are just Python scripts, you can test them with

```bash
pytest test_notebook.py
```

[`pytest`](https://docs.pytest.org/en/stable/), a popular testing framework
for Python, will run all the tests in `test_notebook.py` and show you the
results. For example the following notebook:

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

will produce the following output:

```pytest
============================= test session starts ==============================
platform linux -- Python 3.11.10, pytest-8.3.3, pluggy-1.5.0
rootdir: /notebooks
configfile: pyproject.toml
collected 2 items

examples.py F.                                                           [100%]

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
    def test_fails(inc):
>       assert inc(3) == 5, "This test fails"
E       AssertionError: This test fails

examples.py:16: AssertionError
=========================== short test summary info ============================
FAILED examples.py::test_fails - AssertionError: This test fails
========================= 1 failed, 1 passedin 0.20s ===========================
```

!!! note "You can use marimo notebooks just like normal pytest tests"

    You can include these notebooks in your standard test suite and
    `pytest` just like any other python script.


## pytest fixtures

A powerful feature of `pytest` is the ability to define
[fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html#about-fixtures).
Fixtures and are reliable ways to set up, tear down or mock resources for your
tests. marimo uses function arguments to denote variable dependencies, but
variables ending in `_fixture` will be treated as fixtures in `pytest`.
For example:

```python
# content of conftest.py
import pytest

@pytest.fixture
def working_requests_fixture():
    def pass_request():
        return "apple"
    return request_fixture


@pytest.fixture
def failing_requests_fixture():
    def fail_request():
        raise Exception("Request failed")
    return request_fixture


@pytest.fixture(params=["working_request_fixture", "failing_request_fixture"])
def requests_fixture(request: Any) -> Kernel:
    return request.getfixturevalue(request.param)
```

```python
# content of test_notebook.py
import marimo

__generated_with = "0.10.6"
app = marimo.App()


@app.cell
def _():
    import requests
    requests_fixture = requests.get
    return requests, requests_fixture

# ... normal usage

@app.cell
def test_sanity(my_obj, requests_fixture):
    my_obj.get = requests_fixture
    assert (
        my_obj.execute(),
        f"Test issue with {requests_fixture.__name__}"
    )
```
