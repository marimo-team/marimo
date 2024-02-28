import marimo

__generated_with = "0.2.8"
app = marimo.App()


@app.cell
def make_slider():
    import marimo as mo

    slider = mo.ui.slider(0, 10)
    slider
    return (mo, slider)


if __name__ == "__main__":
    app.run()
