import marimo

__generated_with = "0.8.17"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
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
    return euclid_mcd,


@app.cell
def __(euclid_mcd):
    euclid_mcd(42, 42)
    return


@app.cell
def __():
    def bad_multiply_by_2(a: int) -> int:
        """Multiply a by 2 and return the result.

        >>> bad_multiply_by_2(2)
        4
        >>> bad_multiply_by_2(3)
        6
        """
        return a + 2
    return bad_multiply_by_2,


@app.cell
def __(bad_multiply_by_2, euclid_mcd, mo):
    # Including these make this doctest reactive
    euclid_mcd
    bad_multiply_by_2

    import doctest
    failures, success = doctest.testmod(verbose=True)
    mo.md(f"Success: {success}, Failures: {failures}")
    return doctest, failures, success


if __name__ == "__main__":
    app.run()
