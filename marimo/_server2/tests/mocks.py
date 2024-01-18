import functools
import tempfile

from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager


@functools.lru_cache()
def get_mock_session_manager() -> SessionManager:
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)

    temp_file.write(
        """
import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    mo.md("# Hello Marimo!")
    return mo,


if __name__ == "__main__":
    app.run()
""".encode()
    )

    return SessionManager(
        filename=temp_file.name,
        mode=SessionMode.EDIT,
        port=1001,
        development_mode=False,
        quiet=False,
        include_code=True,
    )
