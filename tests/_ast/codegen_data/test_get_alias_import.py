
import marimo as mo

__generated_with = "0.14.11"
app = mo.App()


@app.cell
def one():
    x: int = 0
    return (x,)

if __name__ == "__main__":
    app.run()
