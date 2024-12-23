import marimo

__generated_with = "0.10.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    def euclid_mcd(a: int, b: int) -> int:
        """Return the MCD between positive a, b.
        >>> euclid_mcd(42, 24)
        6
        >>> euclid_mcd(24, 42)
        6
        >>> euclid_mcd(42, 42)
        42
        """
        assert a > 0
        assert b > 0
        if a < b:
            a, b = b, a
        if (a != b):
            r = a - b
            return euclid_mcd(b, r)
        return a
    return (euclid_mcd,)


@app.cell
def _(euclid_mcd, mo):
    # Include a reference to each function to test
    euclid_mcd

    import doctest

    failures, success = doctest.testmod(verbose=True)
    mo.md(f"Success: {success}, Failures: {failures}")
    return doctest, failures, success


if __name__ == "__main__":
    app.run()
