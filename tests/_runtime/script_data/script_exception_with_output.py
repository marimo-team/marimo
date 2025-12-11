# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///
import marimo

__generated_with = "0.6.19"
app = marimo.App()


@app.cell
def __():
    x = 0
    y = 0
    y / x
    return x, y


if __name__ == "__main__":
    app.run()
