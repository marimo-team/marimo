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
from typing import Any
import marimo

generator = marimo.MarimoIslandGenerator()


def get_script_tags(mode: str) -> str:
    """Generate appropriate script tags based on mode.

    Args:
        mode: One of 'cdn', 'local', or 'dev'
    """
    if mode == "dev":
        return """
            <!-- Vite development mode -->
            <script type="module">import { injectIntoGlobalHook } from "/@react-refresh";
            injectIntoGlobalHook(window);
            window.$RefreshReg$ = () => {};
            window.$RefreshSig$ = () => (type) => type;</script>

            <script type="module" src="/@vite/client"></script>
            <script type="module" src="/src/core/islands/main.ts"></script>"""
    elif mode == "local":
        return """
            <!-- Local production build -->
            <script type="module" src="http://127.0.0.1:8001/main.js"></script>
            <link
              href="http://127.0.0.1:8001/style.css"
              rel="stylesheet"
              crossorigin="anonymous"
            />"""
    else:
        return f"""
            {generator.render_head()}"""


def create_examples() -> list[tuple[str, list[Any]]]:
    """Create organized examples showcasing marimo islands features."""
    examples: list[tuple[str, list[Any]]] = []

    # ============================================================================
    # Getting Started
    # ============================================================================
    examples.append(("Getting Started", [
        generator.add_code("import marimo as mo"),
        generator.add_code(
            """
            mo.md(
                \"\"\"
                # 🏝️ marimo Islands Demo

                Welcome! This page demonstrates marimo islands - interactive Python
                code that runs in your browser. Each island is independent and reactive.
                \"\"\"
            )
            """
        ),
    ]))

    # ============================================================================
    # Basic UI Components
    # ============================================================================
    examples.append(("Basic UI Components", [
        generator.add_code(
            """
            mo.md("## Sliders")
            """
        ),
        generator.add_code(
            """
            slider = mo.ui.slider(0, 100, value=50, label="Value")
            slider
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Current value:** {slider.value}")
            """
        ),

        generator.add_code(
            """
            mo.md("## Buttons")
            """
        ),
        generator.add_code(
            """
            counter = mo.ui.button(
                value=0,
                label="Click me!",
                on_click=lambda v: v + 1
            )
            counter
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Button clicked {counter.value} times**")
            """
        ),

        generator.add_code(
            """
            mo.md("## Text Inputs")
            """
        ),
        generator.add_code(
            """
            name_input = mo.ui.text(value="", placeholder="Enter your name")
            name_input
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Hello, {name_input.value or 'stranger'}!**")
            """
        ),

        generator.add_code(
            """
            mo.md("## Dropdowns")
            """
        ),
        generator.add_code(
            """
            color = mo.ui.dropdown(
                options=["red", "blue", "green", "yellow"],
                value="blue",
                label="Choose a color"
            )
            color
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Selected color:** {color.value}")
            """
        ),

        generator.add_code(
            """
            mo.md("## Checkboxes & Switches")
            """
        ),
        generator.add_code(
            """
            checkbox = mo.ui.checkbox(label="Enable feature", value=True)
            switch = mo.ui.switch(label="Dark mode", value=False)

            mo.hstack([checkbox, switch], justify="start", gap=2)
            """
        ),
        generator.add_code(
            """
            mo.md(
                f\"\"\"
                - Checkbox: **{'✓' if checkbox.value else '✗'}**
                - Switch: **{'ON' if switch.value else 'OFF'}**
                \"\"\"
            )
            """
        ),

        generator.add_code(
            """
            mo.md("## Radio Buttons")
            """
        ),
        generator.add_code(
            """
            size = mo.ui.radio(
                options=["Small", "Medium", "Large"],
                value="Medium",
                label="Size"
            )
            size
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Selected size:** {size.value}")
            """
        ),

        generator.add_code(
            """
            mo.md("## Number Inputs")
            """
        ),
        generator.add_code(
            """
            number = mo.ui.number(
                start=0,
                stop=100,
                step=5,
                value=25,
                label="Quantity"
            )
            number
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Quantity:** {number.value}")
            """
        ),
    ]))

    # ============================================================================
    # Advanced UI Components
    # ============================================================================
    examples.append(("Advanced Components", [
        generator.add_code(
            """
            mo.md("## Multiselect")
            """
        ),
        generator.add_code(
            """
            fruits = mo.ui.multiselect(
                options=["Apple", "Banana", "Cherry", "Date", "Elderberry"],
                value=["Apple", "Banana"],
                label="Select fruits"
            )
            fruits
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Selected:** {', '.join(fruits.value) if fruits.value else 'None'}")
            """
        ),

        generator.add_code(
            """
            mo.md("## Range Slider")
            """
        ),
        generator.add_code(
            """
            price_range = mo.ui.range_slider(
                start=0,
                stop=1000,
                value=[100, 500],
                label="Price range"
            )
            price_range
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Price range:** ${price_range.value[0]} - ${price_range.value[1]}")
            """
        ),

        generator.add_code(
            """
            mo.md("## Tabs")
            """
        ),
        generator.add_code(
            """
            tabs = mo.ui.tabs(
                {
                    "Overview": mo.md("## Overview\\n\\nThis is the overview tab."),
                    "Details": mo.md("## Details\\n\\nThis is the details tab."),
                    "Settings": mo.md("## Settings\\n\\nThis is the settings tab."),
                }
            )
            tabs
            """
        ),

        generator.add_code(
            """
            mo.md("## Code Editor")
            """
        ),
        generator.add_code(
            """
            code = mo.ui.code_editor(
                value='print("Hello, marimo!")',
                language="python",
                label="Python code"
            )
            code
            """
        ),
        generator.add_code(
            """
            mo.md(f\"\"\"
            **Code length:** {len(code.value)} characters
            \"\"\")
            """
        ),
    ]))

    # ============================================================================
    # Data Display
    # ============================================================================
    examples.append(("Data Display", [
        generator.add_code(
            """
            mo.md("## Tables")
            """
        ),
        generator.add_code(
            """
            import pandas as pd

            df = pd.DataFrame({
                "Name": ["Alice", "Bob", "Charlie"],
                "Age": [25, 30, 35],
                "City": ["New York", "London", "Tokyo"]
            })

            table = mo.ui.table(df, label="User Data")
            table
            """
        ),

        generator.add_code(
            """
            mo.md("## Markdown Rendering")
            """
        ),
        generator.add_code(
            """
            mo.md(
                \"\"\"
                ### Rich Text Support

                marimo supports **bold**, *italic*, and `code` formatting.

                - Lists work great
                - With multiple items
                - And nested sub-items

                > Blockquotes are also supported!
                \"\"\"
            )
            """
        ),

        generator.add_code(
            """
            mo.md("## LaTeX Math")
            """
        ),
        generator.add_code(
            """
            mo.md(
                r\"\"\"
                ### Mathematical Expressions

                Inline math: $E = mc^2$

                Display math:

                $$
                \\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}
                $$

                Complex equations:

                $$
                \\nabla \\times \\mathbf{F} = \\left( \\frac{\\partial F_z}{\\partial y} - \\frac{\\partial F_y}{\\partial z} \\right) \\mathbf{i} + \\cdots
                $$
                \"\"\"
            )
            """
        ),
    ]))

    # ============================================================================
    # Layout & Composition
    # ============================================================================
    examples.append(("Layout & Composition", [
        generator.add_code(
            """
            mo.md("## Layout Components")
            """
        ),
        generator.add_code(
            """
            x = mo.ui.slider(0, 10, value=5, label="X")
            y = mo.ui.slider(0, 10, value=5, label="Y")

            mo.hstack([x, y], justify="start", gap=2)
            """
        ),
        generator.add_code(
            """
            mo.md(f"**Position:** ({x.value}, {y.value})")
            """
        ),

        generator.add_code(
            """
            mo.md("## Forms")
            """
        ),
        generator.add_code(
            """
            form = mo.ui.form(
                mo.ui.dictionary(
                    {
                        "name": mo.ui.text(placeholder="Name"),
                        "email": mo.ui.text(placeholder="Email"),
                        "age": mo.ui.number(start=0, stop=120, value=25),
                    }
                ),
                submit_button_label="Submit"
            )
            form
            """
        ),
        generator.add_code(
            """
            if form.value:
                v = form.value
                mo.md(
                    f\"\"\"
                    **Form submitted!**

                    - Name: {v['name']}
                    - Email: {v['email']}
                    - Age: {v['age']}
                    \"\"\"
                )
            else:
                mo.md("Fill out the form above and click submit.")
            """
        ),
    ]))

    # ============================================================================
    # Island Features
    # ============================================================================
    examples.append(("Island Features", [
        generator.add_code(
            """
            mo.md("## Display Code")
            """
        ),
        generator.add_code(
            """
            mo.md("You can show the code that generated this island!")
            """,
            display_code=True
        ),

        generator.add_code(
            """
            mo.md("## Non-Reactive Islands")
            """
        ),
        generator.add_code(
            """
            mo.md(
                \"\"\"
                This island is non-reactive - it runs once and doesn't update
                when other islands change. Perfect for expensive computations
                or static content.
                \"\"\"
            )
            """,
            is_reactive=False
        ),

        generator.add_code(
            """
            mo.md("## Combined Features")
            """
        ),
        generator.add_code(
            """
            # This island shows code AND is non-reactive
            mo.md("Static content with code visible")
            """,
            display_code=True,
            is_reactive=False
        ),
    ]))

    # ============================================================================
    # Error Handling
    # ============================================================================
    examples.append(("Error Handling", [
        generator.add_code(
            """
            mo.md("## Error Display")
            """
        ),
        generator.add_code(
            """
            # This will raise an error
            import nonexistent_module
            "This won't execute"
            """
        ),
    ]))

    return examples


def render_section_divider(title: str) -> str:
    """Render a section divider."""
    return f"""
        <hr style="margin: 1rem 0; border: none; border-top: 2px solid #e5e7eb;" />
        <div style="margin: 1rem 0;">
            <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">
                {title}
            </h2>
        </div>
    """


def run(mode: str):
    """Generate and print the HTML output."""
    examples = create_examples()

    # Build all islands
    app = asyncio.run(generator.build())

    script_tags = get_script_tags(mode)

    # Render all stubs
    rendered_sections: list[str] = []
    for section_title, stubs in examples:
        rendered_sections.append(render_section_divider(section_title))
        rendered_sections.extend([stub.render() for stub in stubs])

    # Add Tailwind test section
    tailwind_test = """
        <hr style="margin: 1rem 0; border: none; border-top: 2px solid #e5e7eb;" />
        <div style="margin: 1rem 0;">
            <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">
                Tailwind CSS Isolation Test
            </h2>
        </div>
        <div class="bg-background p-4 border-2 text-primary font-bold bg-background">
            This should NOT be affected by global Tailwind styles
        </div>
        <div class="marimo">
            <div class="bg-background p-4 border-2 text-primary font-bold text-foreground">
                This SHOULD be affected by global Tailwind styles
            </div>
        </div>
        <div class="marimo">
            <div class="dark">
                <div class="bg-background p-4 border-2 text-primary font-bold text-foreground">
                    This SHOULD be affected by global Tailwind styles (dark mode)
                </div>
            </div>
        </div>
    """

    output = f"""
<!doctype html>
<html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#000000" />
        <meta name="description" content="marimo islands demo - interactive Python in the browser" />
        <title>🏝️ marimo Islands Demo</title>

        {script_tags}
    </head>
    <body style="max-width: 1200px; margin: 0 auto; padding: 1rem; font-family: system-ui, -apple-system, sans-serif;">

        {dedent("".join(rendered_sections))}

        {tailwind_test}

    </body>
</html>
    """

    print(output)


if __name__ == "__main__":
    run(os.environ.get("MODE", "cdn"))
