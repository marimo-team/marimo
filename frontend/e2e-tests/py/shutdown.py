import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    print('123')
    return


if __name__ == "__main__":
    app.run()
