import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Baseline: a few horizontal tabs

    Should look identical to pre-fix behavior — no scrollbar shown,
    nothing visually changed.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {
            "Hello": mo.md("Hello, world! 👋"),
            "Goodbye": mo.md("See you later."),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Many horizontal tabs

    With 100 tabs, the tab bar should be **horizontally scrollable** — every
    tab is reachable. Try scrolling with the trackpad/mouse wheel and using
    the keyboard arrow keys after focusing a tab.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs({f"tab-{i:02d}": mo.md(f"content {i}") for i in range(100)})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Long labels in horizontal tabs

    Long labels should not wrap inside a single trigger; the tab bar
    scrolls horizontally instead.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {
            "A reasonably descriptive section title": mo.md("A"),
            "Another wordy heading that takes up space": mo.md("B"),
            "Yet another deliberately verbose tab label": mo.md("C"),
            "And one more for good measure to force overflow": mo.md("D"),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Many tabs, **vertical** orientation

    With `orientation="vertical"`, tabs stack on the left and content
    appears on the right.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {f"Section {i:02d}": mo.md(f"### Content {i}") for i in range(20)},
        orientation="vertical",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Vertical orientation with rich content
    """)
    return


@app.cell
def _(mo):
    _user = mo.vstack(
        [
            mo.md("**Edit user**"),
            mo.ui.text(label="First name", value="Ada", placeholder="First name"),
            mo.ui.text(
                label="Last name", value="Lovelace", placeholder="Last name"
            ),
            mo.ui.text(
                label="Email",
                value="ada@example.com",
                placeholder="name@example.com",
            ),
            mo.ui.text(
                label="Phone",
                value="+1 (555) 123-4567",
                placeholder="+1 (555) ...",
            ),
            mo.ui.dropdown(
                options=[
                    "Developer",
                    "Designer",
                    "Product Manager",
                    "Admin",
                    "Other",
                ],
                value="Developer",
                label="Role",
            ),
        ]
    )
    _org = mo.vstack(
        [
            mo.md("**Edit organization**"),
            mo.ui.text(
                label="Organization",
                value="marimo",
                placeholder="Organization name",
            ),
            mo.ui.text(
                label="Website",
                value="https://marimo.ai",
                placeholder="https://...",
            ),
            mo.ui.number(label="Employees", start=0, stop=10000, value=42),
            mo.ui.dropdown(
                options=[
                    "Software",
                    "Healthcare",
                    "Finance",
                    "Education",
                    "Non-profit",
                    "Other",
                ],
                value="Software",
                label="Industry",
            ),
        ]
    )
    mo.ui.tabs(
        {"🧙 User": _user, "🏢 Organization": _org},
        orientation="vertical",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Labeled tabs that overflow

    The label is rendered above the (scrollable) tab bar, and the tab bar
    still scrolls horizontally rather than getting clipped.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {f"option-{i:02d}": mo.md(f"option body {i}") for i in range(30)},
        label="Pick an option",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. `lazy=True` + many tabs

    Switching tabs should still work; only the active tab's content gets
    materialized. Inspect the DOM and confirm that `marimo-lazy` placeholders
    are present for inactive tabs.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {f"lazy-{i:02d}": mo.md(f"lazy content {i}") for i in range(40)},
        lazy=True,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. Markdown in tab labels

    Tab labels are interpreted as markdown — bold/inline code/emoji should
    all render in the trigger, and the bar should still scroll.
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {
            "**Bold**": mo.md("Bold tab"),
            "`code`": mo.md("Code tab"),
            "🚀 Launch": mo.md("Launch tab"),
            "🌗 Theme": mo.md("Theme tab"),
            "_italic_": mo.md("Italic tab"),
            "Plain text": mo.md("Plain tab"),
            "More 1": mo.md("..."),
            "More 2": mo.md("..."),
            "More 3": mo.md("..."),
            "More 4": mo.md("..."),
            "More 5": mo.md("..."),
            "More 6": mo.md("..."),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. Invalid orientation raises

    Verify that passing a bad `orientation` value raises a clear
    `ValueError`.
    """)
    return


@app.cell
def _(mo):
    # Expected to fail
    mo.ui.tabs({"a": "1"}, orientation="diagonal")
    return


if __name__ == "__main__":
    app.run()
