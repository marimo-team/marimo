# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# [tool.uv.sources]
# marimo = { path = "../../", editable = true }
# ///
"""
Generate demo HTML for marimo islands.

Usage:
    # Generate and save to file (for production)
    uv run ./islands/generate.py > islands/__demo__/index.html

    # Generate for local development (auto-injected by Vite)
    pnpm dev:islands

    # Generate with specific mode
    MODE=cdn uv run ./islands/generate.py      # Use CDN (default)
    MODE=local uv run ./islands/generate.py    # Use local build
    MODE=dev uv run ./islands/generate.py      # Use Vite dev server
"""

import asyncio
import os
from textwrap import dedent
import marimo

generator = marimo.MarimoIslandGenerator()


def get_script_tags(mode: str) -> str:
    """Generate appropriate script tags based on mode.

    Args:
        mode: One of 'cdn', 'local', or 'dev'
    """
    if mode == "dev":
        # Vite dev server with HMR
        return """
            <!-- Vite development mode -->
            <script type="module" src="/src/core/islands/main.ts"></script>"""
    elif mode == "local":
        # Local production build
        return """
            <!-- Local production build -->
            <script type="module" src="http://127.0.0.1:8001/main.js"></script>
            <link
              href="http://127.0.0.1:8001/style.css"
              rel="stylesheet"
              crossorigin="anonymous"
            />"""
    else:
        # CDN (default)
        return f"""
            {generator.render_head()}"""


def run(mode: str):

    stubs = [
        # Basic
        generator.add_code("import marimo as mo"),
        generator.add_code("mo.md('Hello, islands!')"),

        # Slider
        generator.add_code(
            """
        slider = mo.ui.slider(0, 100, 2)
        slider
        """
        ),
        generator.add_code(
            """
        mo.md(f"Slider value: {slider.value}")
        """
        ),

        # display_code=True
        generator.add_code("""
        mo.md("We can also show the island code!")
        """, display_code=True),

        # is_reactive=False
        generator.add_code("""
        # Also run expensive outputs without performing them in the browser
        import matplotlib.pyplot as plt
        import numpy as np
        x = np.linspace(0, 2*np.pi, 100)
        y = np.sin(x)
        plt.plot(x, y)
        plt.gca()
        """, display_code=True, is_reactive=False),

        # Error
        generator.add_code(
        """
        import idk_package
        "Should raise an error"
        """
        ),

        # Markdown
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

        # LaTeX
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


    script_tags = get_script_tags(mode)

    NEW_LINE = "\n"
    output = f"""
    <!doctype html>
    <html>
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <meta name="theme-color" content="#000000" />
            <meta name="description" content="a marimo app" />
            <title>🏝️ marimo islands demo</title>

            {script_tags}
        </head>
        <body>

    {dedent(NEW_LINE.join([stub.render() for stub in stubs]))}


        <br />
        <br />
        <br />
        <br />
        <hr />
        <div class="bg-background p-4 border-2 text-primary font-bold bg-background">
        this should not be affected by global tailwind styles
        </div>
        <div class="marimo">
        <div class="bg-background p-4 border-2 text-primary font-bold text-foreground">
            this should be affected by global tailwind styles
        </div>
        </div>
        <div class="marimo">
        <div class="dark">
            <div class="bg-background p-4 border-2 text-primary font-bold text-foreground">
            this should be affected by global tailwind styles (dark)
            </div>
        </div>
        </div>
        </div>

        </body>
    </html>
    """

    print(output)


if __name__ == "__main__":
    run(os.environ.get("MODE", "cdn"))
