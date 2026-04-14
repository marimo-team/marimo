import marimo

__generated_with = "0.23.1"
app = marimo.App()

with app.setup:
    import marimo as mo


@app.cell
def _():
    mo.md("""
    # Virtual Files + Process Isolation Smoke Test

    This notebook creates virtual files (HTML, image, Arrow) to verify they
    are served correctly when the app runs in an isolated subprocess
    (`isolate_apps=true`).

    **Bug:** When `isolate_apps` is enabled, the kernel runs in a child
    process that stores virtual files in process-local `InMemoryStorage`.
    The server process cannot access them, causing `FileNotFoundError`
    when the browser requests `/@file/...`.

    **How to test:**

    ```
    marimo run marimo/_smoke_tests/process_isolation/virtual_files.py \\
               marimo/_smoke_tests/process_isolation/app1.py
    ```

    Multi-file `marimo run` auto-enables process isolation. If all three
    sections below render correctly (not broken images / empty iframes),
    virtual file serving across process boundaries is working.
    """)
    return


@app.cell
def _():
    import struct
    import zlib

    def _make_tiny_png(r: int, g: int, b: int) -> bytes:
        """Create a minimal valid 1x1 PNG with the given RGB colour."""

        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            return (
                struct.pack(">I", len(data))
                + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            )

        header = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw_row = b"\x00" + bytes([r, g, b])
        idat = _chunk(b"IDAT", zlib.compress(raw_row))
        iend = _chunk(b"IEND", b"")
        return header + ihdr + idat + iend

    png_bytes = _make_tiny_png(0, 128, 255)

    mo.vstack([
        mo.md(
            "## 1. Image virtual file\n\n"
            "If you see a small blue square below, the image virtual "
            "file was served successfully."
        ),
        mo.image(src=png_bytes, width=64, height=64),
    ])
    return


@app.cell
def _():
    # Use mo.ui.table with a small dataset — tables produce .arrow virtual
    # files under the hood.
    table = mo.ui.table(
        [
            {"name": "Alice", "score": 95},
            {"name": "Bob", "score": 87},
            {"name": "Charlie", "score": 72},
        ],
    )

    mo.vstack([
        mo.md(
            "## 2. Table (Arrow virtual file)\n\n"
            "If the table renders with three rows below, the Arrow "
            "virtual file was served successfully."
        ),
        table,
    ])
    return


if __name__ == "__main__":
    app.run()
