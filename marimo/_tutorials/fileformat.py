# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.69"
app = marimo.App()


@app.cell(hide_code=True)
def __(intro, mo):
    mo.md(intro)
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: hide this tutorial's code": (
            """
            Click the app window icon in the bottom-left to hide this app's code,
            or use the "fold code" shortcut to fold all code cells.
            """
            )
        }
    )
    return


@app.cell(hide_code=True)
def __(example_program, mo):
    mo.md(example_program)
    return


@app.cell(hide_code=True)
def __(file_contents, mo):
    mo.md(file_contents)
    return


@app.cell(hide_code=True)
def __(mo):
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
def __(mo, properties):
    mo.accordion(properties)
    return


@app.cell(hide_code=True)
def __():
    intro = """
    # File Format

    marimo apps are stored as pure Python files.

    These files are:

    - easily versioned with git, producing small diffs
    - legible for both humans and machines
    - formattable using your tool of choice
    - usable as Python  scripts, with UI  elements taking their default values
    """
    return intro,


@app.cell(hide_code=True)
def __(mo):
    file_contents = f"""
        For the above example, marimo would generate the following file 
        contents:

        ```python3
        import marimo

        __generated_with = "{mo.__version__}"
        app = marimo.App()

        @app.cell
        def __(text):
            print(text.value)
            return

        @app.cell
        def __(mo):
            text = mo.ui.text(value="Hello, World!")
            text
            return text,

        @app.cell
        def __():
            import marimo as mo
            return mo,

        if __name__ == "__main__":
            app.run()
        ```

        As you can see, this is _pure Python_. This is part of the reason why
        marimo's generated files are **git-friendly**: small changes made using 
        the marimo editor result in small changes to the file that marimo 
        generates.
    """
    return file_contents,


@app.cell(hide_code=True)
def __():
    example_program = """
    ## Example

    Consider a marimo notebook with the following three cells.

    First cell:
    ```python3
    print(text.value)
    ```

    Second cell:
    ```python3
    text = mo.ui.text(value="Hello, World!")
    text
    ```

    Third cell:
    ```python3
    import marimo as mo
    ```
    """
    return example_program,


@app.cell(hide_code=True)
def __():
    properties = {
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
        def __(mo):
            text = mo.ui.text(value="Hello, World!")
            text
            return text,
        ```

        says that the cell takes as input a variable called `mo`, and it creates
        a global variable called `text`.

        In contrast, the code

        ```python3
        @app.cell
        def __():
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
        Ruff, and be confident that your changes will be preserved.
        """,
        "Cell functions can have names": """
        If you want to, you can replace the default names for cell functions 
        with meaningful ones.

        For example, change

        ```python3
        @app.cell
        def __(text):
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
        "Helpful error messages": """
        If when editing a cell, you forget to include all a cell's refs in its
        argument list, or all its defs in its returns, marimo will raise a 
        helpful error message the next time you try to open it in the marimo 
        editor. So don't worry that you'll botch a cell's signature when editing 
        it.
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
    }
    return properties,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
