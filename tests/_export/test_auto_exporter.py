import asyncio
import threading
from pathlib import Path

from marimo._export.exporter import AutoExporter


async def test_newer_auto_export_supersedes_an_older_write(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "marimo._export.exporter.notebook_output_dir",
        lambda _path: tmp_path,
    )
    exporter = AutoExporter()
    try:
        older_write_started = threading.Event()
        release_older_write = threading.Event()

        def write_file(filepath: Path, content: str) -> None:
            if content == "older":
                older_write_started.set()
                assert release_older_write.wait(timeout=2)
            filepath.write_text(content)

        monkeypatch.setattr(exporter, "_write_file_sync", write_file)
        older = exporter.reserve_revision("notebook.py", "html")
        older_task = asyncio.create_task(
            exporter.save_html("notebook.py", "older", revision=older)
        )
        assert await asyncio.to_thread(older_write_started.wait, 2)

        newer = exporter.reserve_revision("notebook.py", "html")
        newer_task = asyncio.create_task(
            exporter.save_html("notebook.py", "newer", revision=newer)
        )
        release_older_write.set()

        assert not await older_task
        assert await newer_task
        assert (tmp_path / "notebook.html").read_text() == "newer"
    finally:
        exporter.cleanup()
