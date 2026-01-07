import marimo

__generated_with = "0.18.4"
app = marimo.App()


@app.cell
def _():
    import matplotlib.pyplot as plt
    plt.plot([1, 2])
    plt.gca()
    return


if __name__ == "__main__":
    app.run()
