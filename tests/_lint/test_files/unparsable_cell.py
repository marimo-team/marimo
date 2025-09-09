import marimo

__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def _():
    x = 1
    return (x,)

# This should create an unparsable cell
app._unparsable_cell("""
x = 1 +  # Syntax error
""")

@app.cell
def __():
    y = 2
    return (y,)

if __name__ == "__main__":
    app.run()
