import marimo

__generated_with = "0.8.17"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo

    return (mo,)


@app.cell
def __(mo):
    mo.md("""# Toast Notification Test""")
    return


@app.cell
def __(mo):
    def show_toast(title, description="", kind=None):
        mo.status.toast(title, description, kind)
        return None

    return (show_toast,)


@app.cell
def __(mo):
    simple_toast = mo.ui.checkbox(label="Simple Toast")
    html_toast = mo.ui.checkbox(label="Toast with HTML description")
    danger_toast = mo.ui.checkbox(label="Danger Toast")
    return danger_toast, html_toast, simple_toast


@app.cell
def __(mo):
    mo.md("""Select a checkbox to trigger a toast notification:""")
    return


@app.cell
def __(danger_toast, html_toast, mo, simple_toast):
    mo.vstack(
        [
            simple_toast,
            html_toast,
            danger_toast,
        ]
    )
    return


@app.cell
def __(danger_toast, html_toast, show_toast, simple_toast):
    if simple_toast.value:
        show_toast("Simple Toast", "This is a basic toast notification")

    if html_toast.value:
        show_toast(
            "HTML Toast", "<b>Bold</b> and <i>italic</i> text in description"
        )

    if danger_toast.value:
        show_toast("Error Occurred", "Something went wrong!", kind="danger")
    return


if __name__ == "__main__":
    app.run()
