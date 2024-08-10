import marimo

__generated_with = "0.7.19"
app = marimo.App(width="medium")


@app.cell
def __(meow):
    meow
    return


if __name__ == "__main__":
    app.run()
