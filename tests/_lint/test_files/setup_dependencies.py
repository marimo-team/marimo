import marimo

__generated_with = "0.15.2"
app = marimo.App()

with app.setup:
    y = x + 1  # This should trigger MR003 - setup cell dependencies


@app.cell
def _():
    x = 1
    return


if __name__ == "__main__":
    app.run()
