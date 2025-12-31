import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")

with app.setup:
    import pytest

    test_cases = [(1, 2), (1, 3), (1, 5)]

    @pytest.fixture()
    def top_level_fixture():
        return 0


@app.function
@pytest.mark.parametrize(("a", "b"), test_cases)
def test_function(a, b):
    assert a < b


@app.function
def inc(x):
    return x + 1


@app.cell
def collection_of_tests():
    @pytest.fixture()
    def scoped_fixture():
        return 0

    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_answer_base(x, y):
        assert inc(x) == y, "These tests should pass."

    @pytest.mark.parametrize(("x", "y"), test_cases)
    def test_answer_toplevel(x, y, top_level_fixture):
        assert x < y + top_level_fixture, "These tests should pass."

    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_answer_scoped(x, y, scoped_fixture):
        assert inc(x) == y + scoped_fixture, "These tests should pass."

    class TestScopedFixture:
        @pytest.fixture(scope="class")
        def example(self):
            return "value"

        def test_uses_fixture(self, example):
            assert example == "value"

    return


@app.cell
def _():
    return


@app.class_definition
class TestClassDefinitionWithFixtures:
    """Test class defined via @app.class_definition with fixtures."""

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


if __name__ == "__main__":
    app.run()
