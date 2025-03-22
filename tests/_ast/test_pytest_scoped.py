import marimo

__generated_with = "0.11.25"
app = marimo.App(width="medium")


with app.setup:
    import pytest
    import marimo as mo
    test_cases = [(1, 2), (1,3), (1,5)]


@app.cell
def _(pytest, test_cases):
    @pytest.mark.parametrize("a,b", test_cases)
    def test_function(a, b):
        assert a < b
    return (test_function,)


if __name__ == "__main__":
    app.run()
