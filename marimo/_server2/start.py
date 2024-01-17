import uvicorn
from altair import Optional

from marimo._server.sessions import SessionMode, initialize_manager
from marimo._server2.utils.print import print_startup


def start(
    filename: Optional[str],
    mode: SessionMode,
    port: int,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
):
    """
    Start the server.
    """

    initialize_manager(
        filename=filename,
        mode=mode,
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
        port=port,
    )

    uvicorn.run("marimo._server2.main:app", port=port, reload=True)

    if not quiet:
        print_startup(
            filename=filename,
            url=f"http://localhost:{port}",
            run=mode == SessionMode.RUN,
        )
