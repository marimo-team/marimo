# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.12"
app = marimo.App(app_title="marimo for Jupyter users")


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """# marimo for Jupyter users

        This notebook explains important differences between Jupyter and marimo. If you're
        familiar with Jupyter and are trying out marimo for the first time, read on!
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Reactive execution

        The biggest difference between marimo and Jupyter is *reactive execution*.

        Try updating the value of x in the next cell, then run it.
        """
    )
    return


@app.cell
def __():
    x = 0; x
    return x,


@app.cell
def __(x):
    y = x + 1; y
    return y,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        marimo 'reacts' to the change in `x` and automatically recalculates `y`!

        **Explanation.** marimo reads the code in your cells and understands the
        dependences between them, based on the variables that each cell declares and
        references. When you execute one cell, marimo automatically executes all other
        cells that depend on it, not unlike a spreadsheet.

        In contrast, Jupyter requires you to manually run each cell.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        ### Why?

        Reactive execution frees you from the tedious task of manually re-running cells.

        It also ensures that your code and outputs remain in sync:
        
        - You don't have to worry about whether you forgot to re-run a cell.
        - When you delete a cell, its variables are automatically removed from
        program memory. Affected cells are automatically invalidated.
        
        This makes marimo notebooks as reproducible as regular Python scripts.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Interactive elements built-in

        marimo comes with a [large library of UI elements](https://docs.marimo.io/guides/interactivity.html) that are automatically
        synchronized with Python.
        """
    )
    return


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    slider = mo.ui.slider(start=1, stop=10, label="$x$")
    slider
    return slider,


@app.cell
def __(slider):
    slider.value
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        **Explanation.** marimo is both a notebook and a library. Import `marimo as
        mo` and use `mo.ui` to get access to powerful UI elements.

        UI elements assigned to variables are automatically plugged into marimo's
        reactive execution model: interactions automatically trigger execution of
        cells that refer to them.

        In contrast, Jupyter's lack of reactivity makes IPyWidgets difficult to use.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        ## Shareable as apps

        marimo notebooks can be shared as read-only web apps: just serve it with

        ```marimo run your_notebook.py```

        at the command-line.

        Not every marimo notebook needs to be shared as an app, but marimo makes it
        seamless to do so if you want to. In this way, marimo works as a replacement
        for both Jupyter and Streamlit.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        ## Cell order

        In marimo, cells can be arranged in any order — marimo figures out the one true way to execute them based on variable declarations and references (in a ["topologically sorted"](https://en.wikipedia.org/wiki/Topological_sorting#:~:text=In%20computer%20science%2C%20a%20topological,before%20v%20in%20the%20ordering.) order)
        """
    )
    return


@app.cell
def __(z):
    z.value
    return


@app.cell
def __(mo):
    z = mo.ui.slider(1, 10, label="$z$"); z
    return z,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        This lets you arrange your cells in the way that makes the most sense to you. For example, put helper functions and imports at the bottom of a notebook, like an appendix.

        In contrast, Jupyter notebooks implicitly assume a top-to-bottom execution order.
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        rf"""
        ## Re-assigning variables

        marimo disallows variable re-assignment. Here is something commonly done in Jupyter notebooks that cannot be done in marimo:
        """
    )
    return


@app.cell
def __():
    df = 0
    return df,


@app.cell
def __():
    df = 1
    return df,


@app.cell
def __(df):
    results = df.groupby(["my_column"]).sum()
    return results,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        **Explanation.** `results` depends on `df`, but which value of `df` should it use? Reactivity makes it impossible to answer this question in a sensible way, so marimo disallows variable reassignment.

        If you run into this error, here are your options:

        1. combine definitions into one cell
        2. prefix variables with an underscore (`_df`) to make them local to the cell
        3. wrap your code in functions, or give your variables more descriptive names
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        ## Markdown

        marimo only has Python cells, but you can still write Markdown: `import marimo as mo` and use `mo.md` to write Markdown.
        """
    )
    return


@app.cell
def __(mo, slider):
    mo.md(
        f"""
        The value of {slider} is {slider.value}.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        **Explanation.** By lifting Markdown into Python, marimo lets you construct
        dynamic Markdown parametrized by arbitrary Python elements. marimo knows
        how to render its own elements, and you can use `mo.as_html` to render other
        objects, like plots.

        _Tip: toggle a markdown view via `Cmd/Ctrl-Shift-M` in an empty cell._
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        ## Notebook files

        Jupyter saves notebooks as JSON files, with outputs serialized in them. This is helpful as a record of your plots and other results, but makes notebooks difficult to version and reuse.

        ### marimo notebooks are Python scripts
        marimo notebooks are stored as pure Python scripts. This lets you version them with git, execute them with the command line, and re-use logic from one notebook in another.

        ### marimo notebooks do not store outputs
        marimo does _not_ save your outputs in the file; if you want them saved, make sure to save them to disk with Python, or export to HTML via the notebook menu.

        ### marimo notebooks are versionable with git

        marimo is designed so that small changes in your code yield small git diffs!
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        ## Parting thoughts

        marimo is a **reinvention** of the Python notebook as a reproducible, interactive, and shareable Python program, instead of an error-prone scratchpad.

        We believe that the tools we use shape the way we think — better tools, for better minds. With marimo, we hope to provide the Python community with a better programming environment to do research and communicate it; to experiment with code and share it; to learn computational science and teach it.

        The marimo editor and library have many features not discussed here.
        Check out [our docs](https://docs.marimo.io/) to learn more!
        
        _This guide was adapted from [Pluto for Jupyter
        users](https://featured.plutojl.org/basic/pluto%20for%20jupyter%20users).
        We ❤️ Pluto.jl!_
        """
    )
    return


if __name__ == "__main__":
    app.run()
