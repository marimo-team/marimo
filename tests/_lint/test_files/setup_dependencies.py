import marimo

__generated_with = "0.15.2"
app = marimo.App()

x = 1

with app.setup:
    y = x + 1  # This should trigger MR003 - setup cell dependencies


@app.cell
def _():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
