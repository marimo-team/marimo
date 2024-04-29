#!/usr/bin/env python3

import asyncio
from textwrap import dedent
from marimo import experimental_MarimoIslandGenerator

generator = experimental_MarimoIslandGenerator()


def run():

    stubs = [
        generator.add_code("import marimo as mo"),
        generator.add_code("mo.md('Hello, islands!')"),
        generator.add_code(
            """
        slider = mo.ui.slider(0, 100, 2)
        slider
        """
        ),
        generator.add_code("""
        mo.md("We can also show the island code!")
        """, include_code=True),
        generator.add_code("""
        # Also run expensive outputs without performing them in the browser
        import matplotlib.pyplot as plt
        import numpy as np
        x = np.linspace(0, 2*np.pi, 100)
        y = np.sin(x)
        plt.plot(x, y)
        plt.gca()
        """, include_code=True, is_reactive=False),
        generator.add_code(
            """
        mo.md(f"Slider value: {slider.value}")
        """
        ),
        generator.add_code(
            """
        mo.md(
            \"\"\"
            # Hello, Markdown!

            Use marimo's "`md`" function to embed rich text into your marimo
            apps. This function compiles Markdown into HTML that marimo
            can display.

            For example, here's the code that rendered the above title and
            paragraph:

            ```python3
            mo.md(
                '''
                # Hello, Markdown!

                Use marimo's "`md`" function to embed rich text into your marimo
                apps. This function compiles your Markdown into HTML that marimo
                can display.
                '''
            )
            ```
            \"\"\"
        )
        """
        ),
        generator.add_code(
            """
        mo.md(
            r\"\"\"
            ## LaTeX
            You can embed LaTeX in Markdown.

            For example,

            ```python3
            mo.md(r'$f : \mathbf{R} \to \mathbf{R}$')
            ```

            renders $f : \mathbf{R} \to \mathbf{R}$, while

            ```python3
            mo.md(
                r'''
                \[
                f: \mathbf{R} \to \mathbf{R}
                \]
                '''
            )
            ```

            renders the display math

            \[
            f: \mathbf{R} \to \mathbf{R}.
            \]
            \"\"\"
        )
        """
        ),
    ]

    app = asyncio.run(generator.build())

    NEW_LINE = "\n"
    output = f"""
    <!doctype html>
    <html>
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <meta name="theme-color" content="#000000" />
            <meta name="description" content="a marimo app" />
            <title>🏝️</title>

            {generator.render_head()}

            <!-- If running a local server of the production build -->
            <!-- <script type="module" src="http://127.0.0.1:8001/main.js"></script>
            <link
              href="http://127.0.0.1:8001/style.css"
              rel="stylesheet"
              crossorigin="anonymous"
            /> -->
        </head>
        <body>

    {dedent(NEW_LINE.join([stub.render() for stub in stubs]))}


        <br />
        <br />
        <br />
        <br />
        <hr />
        <div class="bg-blue-500 p-4 border-2 border-red-500 bg-background">
        this should not be affected by global tailwind styles
        </div>
        <div class="marimo">
        <div class="bg-background p-4 border-2 border-red-500 text-foreground">
            this should be affected by global tailwind styles
        </div>
        </div>
        <div class="marimo">
        <div class="dark">
            <div class="bg-background p-4 border-2 border-red-500 text-foreground">
            this should be affected by global tailwind styles (dark)
            </div>
        </div>
        </div>

        </body>
    </html>
    """

    print(output)


if __name__ == "__main__":
    run()
