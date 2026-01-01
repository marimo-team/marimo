# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.10"
app = marimo.App()


with app.setup:
    import pytest

    test_cases = [(1, 2), (1, 3), (1, 5)]

    @pytest.fixture()
    def top_level_fixture():
        return "top"


# Fixture defined as @app.function
@app.function
@pytest.fixture
def function_fixture():
    return "function"


@app.function
def inc(x):
    return x + 1


@app.function
@pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5), (0, 1)])
def test_parameterized(x, y):
    assert inc(x) == y, "These tests should pass."


@app.cell
def _(inc):
    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_parameterized_collected(x, y):
        assert inc(x) == y, "These tests should pass."

    class TestParent:
        def test_parent_inner(self):
            assert True

        class TestChild:
            def test_inner(self):
                assert True

    return (
        TestParent,
        test_parameterized_collected,
    )


@app.cell
def _():
    def test_sanity():
        assert True

    def test_failure():
        pytest.fail("Ensure a failure is captured.")

    @pytest.mark.skip(reason="Ensure a skip is captured.")
    def test_skip():
        assert True


@app.cell
def _():
    @pytest.mark.parametrize(("a", "b"), test_cases)
    def test_using_var_in_scope(a, b):
        assert a < b


@app.function
@pytest.mark.parametrize(("a", "b"), test_cases)
def test_using_var_in_toplevel(a, b):
    assert a < b


@app.function
def test_uses_top_level_fixture(top_level_fixture):
    assert top_level_fixture == "top"


# Test parametrize + top-level fixture combination
@app.function
@pytest.mark.parametrize(("a", "b"), [(1, 2), (2, 3)])
def test_parametrize_with_toplevel_fixture(a, b, top_level_fixture):
    assert a < b
    assert top_level_fixture == "top"


# Test using @app.function fixture
@app.function
def test_uses_function_fixture(function_fixture):
    assert function_fixture == "function"


# Test class defined with @app.class_definition that has fixtures
@app.class_definition
class TestClassDefinitionWithFixtures:
    """Class with fixtures defined via @app.class_definition"""

    @pytest.fixture(scope="class")
    def class_scoped_fixture(self):
        return "class_scoped"

    @pytest.fixture()
    def instance_fixture(self):
        return "instance"

    def test_uses_class_fixture(self, class_scoped_fixture):
        assert class_scoped_fixture == "class_scoped"

    def test_uses_instance_fixture(self, instance_fixture):
        assert instance_fixture == "instance"

    @staticmethod
    def test_static_uses_class_fixture(class_scoped_fixture):
        assert class_scoped_fixture == "class_scoped"


@app.cell
def _():
    @pytest.fixture()
    def scoped_fixture():
        return "scoped"

    def test_uses_scoped_fixture(scoped_fixture):
        assert scoped_fixture == "scoped"

    # Test parametrize + scoped fixture combination
    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_parametrize_with_scoped_fixture(x, y, scoped_fixture):
        assert x < y
        assert scoped_fixture == "scoped"


@app.cell
def _():
    class TestWithClassFixture:
        @pytest.fixture(scope="class")
        def class_fixture(self):
            return "class"

        def test_uses_class_fixture(self, class_fixture):
            assert class_fixture == "class"

    return (TestWithClassFixture,)


# Test fixture dependency chains
@app.cell
def _():
    @pytest.fixture
    def base_fixture():
        return "base"

    @pytest.fixture
    def dependent_fixture(base_fixture):
        """Fixture that depends on another cell-scoped fixture."""
        return base_fixture + "_extended"

    def test_fixture_dependency_chain(dependent_fixture):
        """Test only requests dependent_fixture, but base_fixture must also work."""
        assert dependent_fixture == "base_extended"


# Null case: fixture defined in one cell, used in another (should error)
@app.cell
def _():
    @pytest.fixture()
    def isolated_fixture():
        return "isolated"


@app.cell
def _():
    def test_cross_cell_fixture_fails(isolated_fixture):
        """Test uses fixture from different cell - should fail with fixture not found."""
        assert isolated_fixture == "isolated"


# Null case: fixture doesn't exist (should error)
@app.cell
def _():
    def test_missing_fixture(this_fixture_does_not_exist):
        """Test uses non-existent fixture - should fail with fixture not found."""
        pass


if __name__ == "__main__":
    app.run()
