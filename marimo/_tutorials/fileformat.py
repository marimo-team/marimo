# Copyright 2025 Marimo. All rights reserved

import marimo

__generated_with = "0.12.8"
app = marimo.App()

with app.setup:
    import marimo as mo
    import dataclasses

    UIElement = mo.ui._core.ui_element.UIElement


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        # File Format

        marimo apps are stored as pure Python files.

        These files are:

        - 🤖 legible for both humans and machines
        - ✏️ formattable using your tool of choice
        - ➕ easily versioned with git, producing small diffs
        - 🐍 usable as Python  scripts, with UI  elements taking their default values
        """
    )
    return


@app.cell(hide_code=True)
def _():
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
def _():
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
        """
    )
    return


@app.cell(hide_code=True)
def _():
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
def _():
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
        Black, and be confident that your changes will be preserved.
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
            """Usable as a module""": """
        Notebooks, being Python files, can be imported and the cells can
        be used. Read on to see how this can be most effectively utilized.
        """,
        }
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        ## Anatomy of a notebook file

        The details of marimo's file format are important if you want to import
        functions and classes defined in your notebook into other Python modules. If you
        don't intend to do so, you can skip this section.
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        ### Setup Cell

        marimo can serialize functions and classes into the top-level of a file, so you can import them with regular Python syntax:

        ```python
        from my_notebook import my_function
        ```

        In particular, if a cell defines just a single function or class, and if that function or class is pure
        save for references to variables defined in a special **setup cell**, it will be serialized top-level.

        **Setup cell.** Notebooks can optionally include a setup cell with imported
        modules, which are written in the file as:

        <!-- note this setup cell is hardcoded in the playground example -->
        ```python
        with app.setup:
            import marimo as mo
            import dataclasses
        ```

        Modules imported in a setup cell can be used in "top-level" functions or
        classes. You can add the setup cell from the general menu of the editor under:

        ::lucide:diamond-plus:: Add setup cell
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        ### Body cells

        Cells that are not saved as functions or classes are serialized as follows:

        ```python
        @app.cell(hide_code=True) # <- Cell options are also saved to file
        def _(increment, a): # <- Signatures are automatically generated and consist of used references
            message = mo.md(f'''
                `a` incremented is {increment(a)}
            ''')
            return (message,) # <- All used cell definitions are returned

        ```

        The default name of a cell is `_`, but you can explicitly give cells a
        name, as seen below:
        """
    )
    return


@app.cell
def cell_example():
    runtime_definition = "Defined in a normal cell, executed in runtime."

    print("This cell is a normal body cell!")

    "Notice how the last line is output"
    return (runtime_definition,)


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        ### Functions and classes

        marimo directly exposes functions and classes that depend only on variables defined in the setup cell (or on other such functions or classes). For example:

        ```python
        @app.function
        def say_hello(name="World"):
            return f"Hello, {name}"
        ```

        See the following example in the playground below:
        """
    )
    return


@app.function
def function_example():
    """Notice how an indicator in the lower right corner shows this cell is serialized differently"""
    return mo.ui.slider(1, 100)


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        Standalone classes are exposed with the `@app.cell_definition` decorator:

        ```python
        @app.class_definition
        class MyClass: ...
        ```

        Moreover, classes and functions can refer to each other like any other
        Python module. Recursion and directed references are also allowed:
        """
    )
    return


@app.class_definition
@dataclasses.dataclass
class SettingExample:
    """
    TODO: I realized this is probably a poor example because
    the class is not reactive.
    Come up with a better example that is:
    - simple
    - topical
    - useful
    or fix name bindings in ui registry for reactive namespaces.
    """

    temperature: UIElement = dataclasses.field(
        default_factory=function_example
    )
    response_length: UIElement = dataclasses.field(
        default_factory=function_example
    )

    def __post_init__(self):
        self._form = (
            mo.md(
                """
                **Reusable component for something like LLM settings**

                temp: {temperature}

                length: {response_length}
                """
            )
            .batch(
                temperature=self.temperature,
                response_length=self.response_length,
            )
            .form()
        )

    @property
    def value(self):
        return self.form.value

    def _mime_(self):
        return self._form._mime_()


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        /// tip | but why?
        ///
        Given the class we have defined so far, we can now import the component
        into other notebooks.

        ```python
        from mynotebook import SettingExample
        ```
        """
    )
    return


@app.cell
def _():
    form = SettingExample()
    form
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        /// attention | Heads up
        ///

        Not all stand alone functions will be exposed in the module. If your
        function depends on variables that are defined in other cells, then it won't
        be exposed top-level.


        For example, this function will not be exposed:
        """
    )
    return


@app.cell
def wrapped_function_example(runtime_definition):
    def wrapped_function_example():
        """
        This function depends on a variable declared in another cell.
        As a result this function isn't exposed in the file — and the tooltip in the
        bottom-right corner indicates this.
        """
        return runtime_definition
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        ## Playground

        Feel free to check out the source of this notebook, or any notebook to
        get a deeper understand of the file format.

        /// tip | Let's use the magic of marimo :sparkles:

        Any cell in this notebook ending in the name `example` will be rendered
        below as expected. Go back to the examples to play around.
        """
    )
    return


@app.cell(hide_code=True)
def _(response):
    response
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
        ## FAQ

        ### I want to write or edit marimo notebooks in a different editor, what do I need to know?


        Refer to our guide on [using your own editor](https://docs.marimo.io/guides/editor_features/watching/)

        ### I want to import functions from a marimo notebook, what do I need to know?

        See the docs [guide on reusable functions](https://links.marimo.app/reusable-functions) and classes for more details.

        ### I want to run tests on marimo notebooks, what do I need to know?

        marimo notebooks are compatible with pytest. See the documentation [on
        testing](https://docs.marimo.io/guides/testing/) for more information.
        """
    )
    return


@app.cell(hide_code=True)
def _(__file__):
    from textwrap import dedent
    from marimo._ast.app import InternalApp
    from marimo._ast.parse import parse_notebook
    from marimo._ast.codegen import generate_filecontents
    from marimo._ast.cell import CellConfig
    from marimo._ast.app import _AppConfig

    notebook = parse_notebook(__file__)

    _names, _codes, _configs = zip(
        *[
            (cell_def.name, cell_def.code, CellConfig(**cell_def.options))
            for cell_def in notebook.cells
            if cell_def.name.lower().endswith("example")
            or cell_def.name == "setup"
        ]
    )

    response = mo.ui.code_editor(
        generate_filecontents(
            list(_codes),
            list(_names),
            list(_configs),
            config=_AppConfig(),
            _toplevel_fn=True,
        ),
        disabled=True,
    )
    return (response,)


if __name__ == "__main__":
    app.run()
