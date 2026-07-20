import marimo

__generated_with = "0.23.14"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # Toast error formatting smoke test

    Trigger each case and check: wrapping, scrolling, text selection, and copy.
    """)
    return


@app.cell
def cases(mo):
    from html import escape

    LONG_PATH = (
        "/Users/example/Library/Caches/ms-playwright/"
        "chromium_headless_shell-1200/"
        "chrome-headless-shell-mac-arm64/chrome-headless-shell"
    )
    PLAYWRIGHT_ERR = f"""\
BrowserType.launch: Executable doesn't exist at {LONG_PATH}
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝"""
    LONG_STACK = """\
Traceback (most recent call last):
  File "/Users/example/src/marimo/marimo/_server/export/_pdf_raster.py", line 601, in rasterize
    async with async_playwright() as playwright:
  File "/Users/example/src/marimo/marimo/_server/api/endpoints/export.py", line 142, in export_as_pdf
    pdf_bytes = await export_pdf(request)
  File "/Users/example/.local/share/uv/tools/marimo/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 59, in send
    return await self._inner_send(method, dict(params), False)
playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist
"""

    def fire_toast(
        title: str, description: str, *, as_html: bool = False, kind="danger"
    ):
        if as_html:
            description = f'<pre style="margin:0;white-space:pre-wrap;word-break:break-word">{escape(description)}</pre>'
        mo.status.toast(title, description, kind)

    cases = mo.ui.dropdown(
        options={
            "short": "short",
            "long path (single line)": "long_path",
            "playwright ascii box (plain)": "playwright_plain",
            "playwright ascii box (html pre)": "playwright_html",
            "tall traceback (plain)": "tall_plain",
            "tall traceback (html pre)": "tall_html",
            "success (control)": "success",
        },
        value="playwright ascii box (plain)",
        label="Error shape",
    )

    fire = mo.ui.run_button(label="Show toast")
    mo.hstack([cases, fire], justify="start", gap=1)
    return LONG_PATH, LONG_STACK, PLAYWRIGHT_ERR, cases, fire, fire_toast


@app.cell
def trigger(LONG_PATH, LONG_STACK, PLAYWRIGHT_ERR, cases, fire, fire_toast, mo):
    if fire.value:
        choice = cases.value
        if choice == "short":
            fire_toast("Failed to download", "Something went wrong.")
        elif choice == "long_path":
            fire_toast(
                "Failed to download",
                f"BrowserType.launch: Executable doesn't exist at {LONG_PATH}",
            )
        elif choice == "playwright_plain":
            fire_toast("Failed to download", PLAYWRIGHT_ERR)
        elif choice == "playwright_html":
            fire_toast("Failed to download", PLAYWRIGHT_ERR, as_html=True)
        elif choice == "tall_plain":
            fire_toast("Failed to download", LONG_STACK)
        elif choice == "tall_html":
            fire_toast("Failed to download", LONG_STACK, as_html=True)
        elif choice == "success":
            mo.status.toast("All good", "This is a short success toast.")
    return


if __name__ == "__main__":
    app.run()
