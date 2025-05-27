import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one(): return


@app.cell
def two():
    return

# fmt: off
@app.cell
def three(
    ): return

@app.cell
def four(
    ):
    return

# fmt: on

if __name__ == "__main__":
    app.run()
