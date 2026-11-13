import os
import pathlib
import random
import tempfile
import textwrap


def random_modname() -> str:
    filename_chars = "abcdefghijklmopqrstuvwxyz"
    return "".join(random.sample(filename_chars, 20))


def update_file(path: pathlib.Path, code: str) -> None:
    # Advance whole seconds to invalidate timestamp-based bytecode. Publish
    # atomically so the watcher sees the new contents and timestamp together.
    mtime = int(path.stat().st_mtime) + 1
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        updated = pathlib.Path(directory) / path.name
        updated.write_text(textwrap.dedent(code))
        os.utime(updated, (mtime, mtime))
        updated.replace(path)
