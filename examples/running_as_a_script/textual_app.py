# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "textual==3.2.0",
# ]
# ///
"""
Marimo wrapper for the base Textual app example.
Provides a basic clock widget to show the current time.
run with `python textual_app.py`
"""

import marimo

__generated_with = "0.13.10"
app = marimo.App()

with app.setup:
    import marimo as mo
    from datetime import datetime

    from textual.app import App, ComposeResult
    from textual.widgets import Digits


@app.class_definition
class ClockApp(App):
    CSS = """
    Screen { align: center middle; }
    Digits { width: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Digits("")

    def on_ready(self) -> None:
        self.update_clock()
        self.set_interval(1, self.update_clock)

    def update_clock(self) -> None:
        clock = datetime.now().time()
        self.query_one(Digits).update(f"{clock:%T}")


@app.cell
def _():
    app = ClockApp()
    if mo.app_meta().mode == "script":
        app.run()
    # App gives back a basic repr
    app
    return


if __name__ == "__main__":
    app.run()
