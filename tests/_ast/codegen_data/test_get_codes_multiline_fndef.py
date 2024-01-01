import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one(a,
        b,      c,d) -> int:
    # comment
    x = 0 + a + b + c + d
    return x,


if __name__ == "__main__":
    app.run()
