import marimo

__generated_with = "0.0.0"
app = marimo.App()

with app.setup:
    import marimo as mo


@app.cell
def _():
    mo.md("""
    # Hello from setup
    """)


@app.cell
def _():
    x = 42


if __name__ == "__main__":
    app.run()
