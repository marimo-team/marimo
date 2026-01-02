# Note that marimo is not repeated in the imports.

import marimo

__generated_with = "0.0.0"
app = marimo.App()

with app.setup:
    # Special setup cell
    import pytest


@app.function
@pytest.fixture
def example_fixture():
    return "example"


@app.function
def add(a, b):
    return a + b


@app.function
@pytest.mark.parametrize(("a", "b", "c"), [(1, 1, 2), (1, 2, 3)])
def test_add_good(a, b, c):
    assert add(a, b) == c


@app.function
@pytest.mark.xfail(
    reason=("Check test is actually called."),
    raises=AssertionError,
    strict=True,
)
@pytest.mark.parametrize(("a", "b", "c"), [(1, 1, 3), (2, 2, 5)])
def test_add_bad(a, b, c):
    assert add(a, b) == c


@app.function
def test_example_fixture(example_fixture):
    assert example_fixture == "example"


@app.class_definition
class TestClassWorks:
    """Has doc string"""

    def test_sanity(self):
        assert True

    @pytest.mark.parametrize(("a", "b", "c"), [(1, 1, 2), (1, 2, 3)])
    def test_decorated(self, a, b, c):
        assert add(a, b) == c

    @staticmethod
    @pytest.mark.parametrize(("a", "b", "c"), [(1, 1, 2), (1, 2, 3)])
    def test_decorated_static(a, b, c) -> None:
        assert add(a, b) == c


@app.class_definition
class TestClassWithFixtures:
    """Has doc string"""

    @pytest.fixture(scope="class")
    def yields_value(self):
        return "value"

    @pytest.fixture
    def return_value(self):
        return "value"

    def test_yield(self, yields_value) -> None:
        assert yields_value == "value"

    @staticmethod
    def test_yield_static(yields_value) -> None:
        assert yields_value == "value"

    def test_return(self, return_value) -> None:
        assert return_value == "value"

    @staticmethod
    def test_return_static(return_value) -> None:
        assert return_value == "value"


if __name__ == "__main__":
    app.run()
