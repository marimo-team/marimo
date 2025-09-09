import marimo

__generated_with = "0.0.0"
app = marimo.App()

@app.cell
def _():
    x = 1
    return

# This should create an unparsable cell
app._unparsable_cell("""
x = 1 +  # Syntax error
""")

@app.cell
def _():
    y = 2
    return

if __name__ == "__main__":
    app.run()
