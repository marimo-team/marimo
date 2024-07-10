import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    from middle import app as middle
    return middle,


@app.cell
async def __(middle):
    await middle.embed()
    return


if __name__ == "__main__":
    app.run()
