import marimo

__generated_with = '0.1.0'
app = marimo.App()


@app.cell
def __(a,
        b, #   hello,
        c,    # again
        d,) -> int:
    # comment
    # another comment

    # yet another comment
    x = 0 + a + b + c + d
    return x,


if __name__ == "__main__":
    app.run()
