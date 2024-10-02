# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.0"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        # How marimo notebooks run

        Reactive execution is based on a single rule: when a cell is run, all other
        cells that reference any of the global variables it defines run
        automatically.

        To provide reactive execution, marimo creates a dataflow graph out of your
        cells.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        rf"""
        **Tip: disabling automatic execution.**

        marimo lets you disable automatic execution: just go into the notebook settings
        and set

        "Runtime > On Cell Change" to "lazy".

        When the runtime is lazy, after running a cell, marimo marks its
        descendants as stale instead of automatically running them. The lazy
        runtime puts you in control over when cells are run, while still giving
        guarantees about the notebook state.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## References and definitions

        A marimo notebook is a directed acyclic graph in which nodes represent 
        cells and edges represent data dependencies. marimo creates this graph by
        analyzing each cell (without running it) to determine its

        - references ("refs*), the global variables it reads but doesn't define;
        - definitions ("defs"), the global variables it defines.

        There is an edge from one cell to another if the latter cell references any
        global variables defined by the former cell.

        The rule for reactive execution can be restated in terms of the graph: when
        a cell is run, its descendants are run automatically.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Example

        The next four cells plot a sine wave with a given period and amplitude.
        Each cell is labeled with its refs and defs.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: inspecting refs and defs": f"""
            Use `mo.refs()` and `mo.defs()` to inspect the refs and defs of any
            given cell. This can help with debugging complex notebooks.

            For example, here are the refs and defs of this cell:

            {mo.as_html({"refs": mo.refs(), "defs": mo.defs()})}
            """
        }
    )
    return


@app.cell
def __(amplitude, mo, period, plot_wave):
    mo.md(
        f"""
        {mo.as_html(plot_wave(amplitude, period))}

        - `refs: {mo.refs()}`
        - `defs: {mo.defs()}`
        """
    )
    return


@app.cell
def __(mo):
    period = 2 * 3.14159

    mo.md(
        f"""
        - `refs: {mo.refs()}`
        - `defs: {mo.defs()}`
        """
    )
    return (period,)


@app.cell
def __(mo):
    amplitude = 1

    mo.md(
        f"""
        - `refs: {mo.refs()}`
        - `defs: {mo.defs()}`
        """
    )
    return (amplitude,)


@app.cell
def __(matplotlib_installed, mo, np, numpy_installed, plt):
    def plot_wave(amplitude, period):
        if not numpy_installed:
            return mo.md(
                "> Oops! It looks like you don't have `numpy` installed."
            )
        if not matplotlib_installed:
            return mo.md(
                "> Oops! It looks like you don't have `matplotlib` installed."
            )
        x = np.linspace(0, 2 * np.pi, 256)
        plt.plot(x, amplitude * np.sin(2 * np.pi / period * x))
        plt.xlim(0, 2 * np.pi)
        plt.ylim(-2, 2)
        plt.xticks(
            [0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi],
            [0, r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"],
        )
        plt.yticks([-2, -1, 0, 1, 2])
        plt.gcf().set_size_inches(6.5, 2.4)
        return plt.gca()

    mo.md(
        f"""
        - `refs: {mo.refs()}`
        - `defs: {mo.defs()}`
        """
    )
    return (plot_wave,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        🌊 **Try it!** In the above cells, try changing the value `period` or 
        `ampltitude`, then click the run button ( ▷ ) to register your changes. 
        See what happens to the sine wave.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        Here is the dataflow graph for the cells that make the sine wave plot, plus
        the cells that import libraries. Each cell is labeled with its defs. 

        ```
                           +------+               +-----------+
               +-----------| {mo} |-----------+   | {np, plt} |
               |           +---+--+           |   +----+------+
               |               |              |        |
               |               |              |        |
               v               v              v        v
          +----------+   +-------------+   +--+----------+
          | {period} |   | {amplitude} |   | {plot_wave} |
          +---+------+   +-----+-------+   +------+------+
              |                |                  |
              |                v                  |
              |              +----+               |
              +------------> | {} | <-------------+
                             +----+
        ```

        The last cell, which doesn't define anything, produces the plot.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Dataflow programming

        marimo's runtime rule has some important consequences that may seem 
        surprising if you are not used to dataflow programming. We list these
        below.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Execution order is not cell order

        The order in which cells are executed is determined entirely by the
        dataflow graph. This makes marimo notebooks more reproducible than
        traditional notebooks. It also lets you place boilerplate, like
        imports or long markdown strings, at the bottom of the editor.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Global variable names must be unique

        Every global variable can be defined by only one cell. Without this 
        constraint, there would be no way for marimo to know which order to 
        execute cells in.

        If you violate this constraint, marimo provides a helpful
        error message, like below:
        """
    )
    return


@app.cell
def __():
    planet = "Mars"
    planet
    return (planet,)


@app.cell
def __():
    planet = "Earth"
    planet
    return (planet,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        **🌊 Try it!** In the previous cell, change the name `planet` to `home`, 
        then run the cell.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        Because defs must be unique, global variables cannot be modified with
        operators like `+=` or `-=` in cells other than the one that created
        them; these operators count as redefinitions of a name.

        **🌊 Try it!** Get rid of the following errors by merging the next two 
        cells into a single cell.
        """
    )
    return


@app.cell
def __():
    count = 0
    return (count,)


@app.cell
def __():
    count += 1
    return (count,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Underscore-prefixed variables are local to cells

        Global variables prefixed with an underscore are "private" to the cells 
        that define them. This means that multiple cells can define the same 
        underscore-prefixed name, and one cell's private variables won't be
        made available to other cells.

        **Example**.
        """
    )
    return


@app.cell
def __():
    _private_variable, _ = 1, 2
    _private_variable, _
    return


@app.cell
def __():
    _private_variable, _ = 3, 4
    _private_variable, _
    return


@app.cell
def __():
    # `_private_variable` and `_` are not defined in this cell
    _private_variable, _
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Deleting a cell deletes its variables

        Deleting a cell deletes its global variables and 
        then runs all cells that reference them. This prevents severe bugs that 
        can arise when state has been deleted from the editor but not from the 
        program memory.
        """
    )
    return


@app.cell
def __(mo):
    to_be_deleted = "variable still exists"

    mo.md(
        """
        🌊 **Try it!**

        Delete this cell by clicking the trash bin icon.
        """
    )
    return (to_be_deleted,)


@app.cell
def __(to_be_deleted):
    to_be_deleted
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Cycles are not allowed

        Cycles among cells are not allowed. For example:
        """
    )
    return


@app.cell
def __(two):
    one = two - 1
    return (one,)


@app.cell
def __(one):
    two = one + 1
    return (two,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### marimo doesn't track attributes

        marimo only tracks global variables. Writing object attributes does not 
        trigger reactive execution.

        **🌊 Example**. Change the value of `state.number` in the next cell, then
        run the cell. Notice how the subsequent cell isn't updated.
        """
    )
    return


@app.cell
def __(state):
    state.number = 1
    return


@app.cell
def __(state):
    state.number
    return


@app.cell
def __():
    class namespace:
        pass

    state = namespace()
    state.number = 0
    return namespace, state


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Why not track attributes?": """
            marimo can't reliably trace attributes 
            to cells that define them. For example, attributes are routinely 
            created or modified by library code.
            """
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### marimo doesn't track mutations

        In Python, it's impossible to know whether code will 
        mutate an object without running it. So: mutations (such as
        appending to a list) will not trigger reactive execution.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip (advanced): mutable state": (
                """
            You can use the fact that marimo does not track attributes or 
            mutations to implement mutable state in marimo. An example of
            this is shown in the `ui` tutorial.
            """
            )
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Best practices

        The constraints marimo puts on your notebooks are all natural consequences
        of the fact that marimo programs are directed acyclic graphs. As long as 
        you keep this fact in mind, you'll quickly adapt to the marimo way of
        writing notebooks.

        Ultimately, these constraints will enable you to create powerful notebooks
        and apps, and they'll encourage you to write clean, reproducible code.

        Follow these tips to stay on the marimo way:
        """
    )
    return


@app.cell
def __(mo, tips):
    mo.accordion(tips)
    return


@app.cell
def __(mo):
    mo.md(
        """
        ## What's next?

        Check out the tutorial on interactivity for a tour of UI elements:

        ```
        marimo tutorial ui
        ```
        """
    )
    return


@app.cell(hide_code=True)
def __():
    matplotlib_installed = False
    numpy_installed = False

    try:
        import matplotlib.pyplot as plt

        matplotlib_installed = True
    except ModuleNotFoundError:
        pass

    try:
        import numpy as np

        numpy_installed = True
    except ModuleNotFoundError:
        pass
    return matplotlib_installed, np, numpy_installed, plt


@app.cell(hide_code=True)
def __():
    tips = {
        "Use global variables sparingly": (
            """
            Keep the number of global variables in your program small to avoid
            name collisions across cells. Keep the number of global variables 
            defined by any one cell small to make sure that the units of
            reactive execution are small. 
            """
        ),
        "Use descriptive names": (
            """
            Use descriptive variable names, especially for global variables.
            This will help you minimize name clashes, and will also result in
            better code.
            """
        ),
        "Use functions": (
            """
            Encapsulate logic into functions to avoid polluting the global
            namespace with temporary or intermediate variables.
            """
        ),
        "Minimize mutations": (
            """
            We saw earlier that marimo cannot track object mutations. So try
            to only mutate an object in the cell that creates it, or create
            new objects instead of mutating existing ones.

            For example, don't do this:

            ```python3
            # a cell
            numbers = [1, 2, 3]
            ```

            ```python3
            # another cell
            numbers.append(4)
            ```

            Instead, prefer

            ```python3
            # a cell
            numbers = [1, 2, 3]
            numbers.append(4)
            ```

            or

            ```python3
            # a cell
            numbers = [1, 2, 3]
            ```

            ```python3
            # another cell
            more_numbers = numbers + [4]
            ```
            """
        ),
        "Write idempotent cells": (
            """  
            Write cells whose outputs and behavior are the same when given
            the same inputs (refs); such cells are called _idempotent_. This will
            help you avoid bugs, and let you cache expensive intermediate
            computations (see the next tip).
            """
        ),
        "Cache intermediate computations with `@mo.cache`": (
            """
            Use `mo.cache` to cache the return value of expensive functions.
            You can do this if you abstract complex logic into idempotent
            functions, following earlier tips.

            For example:

            ```python3
            import marimo as mo

            @mo.cache
            def compute_prediction(problem_parameters):
              ...
            ```

            Whenever `compute_predictions` is called with a value of
            `problem_parameters` it has not seen, it will compute the predictions
            and store them in a cache. The next time it is called with the same
            parameters, instead of recomputing the predictions, it will just 
            fetch the previously computed ones from the cache.

            If you are familiar with `functools.cache`, `mo.cache` is
            similar but more robust, with the cache persisting even
            if the cell defining the function is re-run.
            """
        ),
    }
    return (tips,)


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
