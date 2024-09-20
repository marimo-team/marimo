from __future__ import annotations

from pathlib import Path

from marimo._output.rich_help import mddoc
from marimo._runtime.state import State, state
from marimo._utils.file_watcher import FileWatcher


@mddoc
def filewatch(filepath: str | Path) -> State[str]:
    """
    Watch a file for changes and update the state with the file content.

    Args:
        filepath (str | Path): path of the file to watch

    Raises:
        FileNotFoundError: If the file does not exist

    Returns: a getter function that returns the content of the file.
    """
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    def read_file_content(file_path: Path) -> str:
        with open(str(file_path), "r") as file:
            return file.read()

    get_content, set_content = state(read_file_content(path))

    async def update_content(file_path: Path) -> None:
        set_content(read_file_content(file_path))

    watcher = FileWatcher.create(path, update_content)
    watcher.start()

    # TODO: Need to register a cleanup function
    # get_context().register_cleanup(watcher.stop)

    return get_content
