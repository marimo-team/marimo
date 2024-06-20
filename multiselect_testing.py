import marimo

__generated_with = "0.6.19"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    large_list = [str(i) for i in range(10000)]
    mo.ui.multiselect(large_list, label="Large List")
    return large_list,


if __name__ == "__main__":
    app.run()
