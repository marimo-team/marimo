# Copyright 2025 Marimo. All rights reserved

import marimo

__generated_with = "0.12.8"
app = marimo.App()

with app.setup:
    import dataclasses
    import random


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # File Format

        marimo apps are stored as pure Python files.

        These files are:

        - 🤖 legible for both humans and machines
        - ✏️ formattable using your tool of choice
        - ➕ easily versioned with git, producing small diffs
        - 🐍 usable as Python  scripts, with UI  elements taking their default values
        - 🧩 modular, exposing functions and classes that can be imported from the notebook
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Example

        Consider a marimo notebook with the following four cells.

        First cell:
        ```python3
        print(text.value)
        ```

        Second cell:
        ```python3
        def say_hello(name="World"):
            return f"Hello, {name}!"
        ```

        Third cell:
        ```python3
        text = mo.ui.text(value=say_hello())
        text
        ```

        Fourth cell:
        ```python3
        import marimo as mo
        ```
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        For the above example, marimo would generate the following file
        contents:

        ```python3
        import marimo

        __generated_with = "0.0.0"
        app = marimo.App()

        @app.cell
        def _(text):
            print(text.value)
            return

        @app.function
        def say_hello(name="World"):
            return f"Hello, {name}!"

        @app.cell
        def _(mo):
            text = mo.ui.text(value="Hello, World!")
            text
            return (text,)

        @app.cell
        def _():
            import marimo as mo
            return mo,

        if __name__ == "__main__":
            app.run()
        ```

        As you can see, this is _pure Python_. This is part of the reason why
        marimo's generated files are **git-friendly**: small changes made using
        the marimo editor result in small changes to the file that marimo
        generates.

        Moreover, the cell defining a single pure function `say_hello` was saved "top-level" in the notebook file, making it possible for you to import it into other Python files or notebooks.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Properties

        marimo's file format was designed to be easy to read and easy
        to work with, while also serving the needs of the marimo library. You can
        even edit the generated file's cells directly, using your favorite text
        editor, and format the file with your favorite code formatter.

        We explain some properties of marimo's file format below.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "Cells are functions": """
        In the `dataflow` tutorial, we saw that cells are like functions mapping
        their refs (the global  variables they uses but don't define) to their
        defs (the global variables they define). The generated code makes this
        analogy explicit.

        In the generated code, there is a function for each cell. The arguments
        of  the function are the cell's refs , and its returned variables are
        its defs.

        For example, the code

        ```python3
        @app.cell
        def _(mo):
            text = mo.ui.text(value="Hello, World!")
            text
            return text,
        ```

        says that the cell takes as input a variable called `mo`, and it creates
        a global variable called `text`.

        In contrast, the code

        ```python3
        @app.cell
        def _():
            import marimo as mo
            return mo,
        ```

        says that the cell doesn't depend on any other cells (its argument list
        is  empty), though it does create the variable `mo` which the previous
        cell requires as input.
        """,
            "Cells are stored in presentation order": """
        Cells are stored in the order that they are arranged in the marimo
        editor. So if you want to rearrange
        your cells using your favorite text editor, just rearrange the
        order that they're defined in the file.
        """,
            "Text formatting is preserved": """
        marimo guarantees that however your source code was
        formatted in the marimo editor is exactly how it will be stored in
        the generated code. For example, whitespace, line breaks, and so on are
        all preserved exactly. This means that you can touch up formatting in
        your text editor, either manually or using automated formatters like
        Black, and be confident that your changes will be preserved.
        """,
            "Cell functions can have names": """
        If you want to, you can replace the default names for cell functions
        with meaningful ones.

        For example, change

        ```python3
        @app.cell
        def _(text):
            print(text.value)
            return
        ```

        to

        ```python3
        @app.cell
        def echo(text):
            print(text.value)
            return
        ```

        This can make the generated code more readable.
        """,
            "No magical tokens": """
        marimo's generated code is pure Python; no magical syntax.
        """,
            "Cell signatures automatically maintained": """
        If when editing a cell, you forget to include all a cell's refs in its
        argument list, or all its defs in its returns, marimo will fix them he next
        time you try to open it in the marimo editor. So don't worry that you'll
        botch a cell's signature when editing it.
        """,
            "The `app` object": """
        At the top of the generated code, a variable named `app` is created.
        This object collects the cells into a dataflow graph, using the `cell`
        decorator.
        """,
            "Runnable as a script": """
        You can run marimo apps as scripts at the command line,
        using Python. This will execute the cells in a
        topologically sorted order, just as they would run if you opened the app
        with `marimo edit`.

        For example: running our example as a script would print `Hello
        World!` to the console.
        """,
            """Usable as a module""": """
        Import top-level functions and classes from the notebook into other
        Python files.
        """,
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Importing functions and classes from notebooks

        The details of marimo's file format are important if you want to import
        functions and classes defined in your notebook into other Python modules. If you
        don't intend to do so, you can skip this section.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ### Declaring imports used by functions and classes

        marimo can serialize functions and classes into the top-level of a file, so you can import them with regular Python syntax:

        ```python
        from my_notebook import my_function
        ```

        In particular, if a cell defines just a single function or class, and if that function or class is pure
        save for references to variables defined in a special **setup cell**, it will be serialized top-level.

        **Setup cell.** Notebooks can optionally include a setup cell that imports modules,
        written in the file as:

        <!-- note this setup cell is hardcoded in the playground example -->
        ```python
        with app.setup:
            import marimo as mo
            import dataclasses
        ```

        Modules imported in a setup cell can be used in "top-level" functions or
        classes. You can add the setup cell from the general menu of the editor under:
        ::lucide:diamond-plus:: Add setup cell.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ### Functions and classes

        Notebook files expose functions and classes that depend only on variables defined in the setup cell (or on other such functions or classes). For example, the following cell:
        """
    )
    return


@app.function
def roll_die():
    """
    A reusable function.

    Notice the indicator in the bottom right of the cell.
    """
    return random.randint(1, 7)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ... is saved in the notebook file as

        ```python
        @app.function
        def roll_die():
            \"""
            A reusable function.

            Notice the indicator in the bottom right of the cell.
            \"""
            return random.randint(1, 7)
        ```


        Making it importable as

        ```python
        from fileformat import roll_die
        ```
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""Standalone classes are also exposed:""")
    return


@app.cell
def SimulationExample(function_example):
    @dataclasses.dataclass
    class SimulationExample:
        n_rolls: int

        def simulate(self) -> list[int]:
            return [function_example() for _ in range(self.n_rolls)]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        This class is saved in the file as

        ```python
        @app.class_definition
        @dataclasses.dataclass
        class SimulationExample:
            n_rolls: int

            def simulate(self) -> list[int]:
                return [function_example() for _ in range(self.n_rolls)]
        ```
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        /// attention | Heads up
        ///

        Not all standalone functions will be exposed in the module. If your
        function depends on variables that are defined in other cells, then it won't
        be exposed top-level.


        For example, this function will not be exposed:
        """
    )
    return


@app.cell
def _():
    variable = 123
    return (variable,)


@app.cell
def wrapped_function_example(variable):
    def not_a_top_level_function():
        """
        This function depends on a variable declared in another cell.

        As a result this function isn't exposed in the file — and the tooltip in the
        bottom-right corner indicates this.
        """
        return variable
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## FAQ

        ### I want to edit notebooks in a different editor, what do I need to know?

        See the docs on [using your own editor](https://docs.marimo.io/guides/editor_features/watching/).

        ### I want to import functions from a marimo notebook, what do I need to know?

        See the docs on [reusable functions and
        classes](https://links.marimo.app/reusable-functions).

        ### I want to run pytest on marimo notebooks, what do I need to know?

        See the docs on [testing](https://docs.marimo.io/guides/testing/).
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## This notebook's source code

        The source code of this notebook is shown below:
        """
    )
    return


@app.cell
def _(__file__):
    with open(__file__, "r", encoding="utf-8") as f:
        contents = f.read()
    return (contents,)


@app.cell
def _(contents, mo):
    mo.ui.code_editor(contents)
    return


if __name__ == "__main__":
    app.run()
