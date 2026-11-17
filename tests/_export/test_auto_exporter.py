import asyncio
import threading
from pathlib import Path

import pytest

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

        def write_file(filepath: Path, content: str) -> bool:
            if content == "older":
                older_write_started.set()
                assert release_older_write.wait(timeout=2)
            filepath.write_text(content)
            return True

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


async def test_auto_export_does_not_write_through_symlinks(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "project" / "notebook.py"
    output_dir = notebook.parent / "__marimo__"
    output_dir.mkdir(parents=True)
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("original")
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    try:
        (output_dir / "notebook.md").symlink_to(outside_file)
        (output_dir / "notebook.html").symlink_to(tmp_path / "dangling.html")
        linked_notebook = tmp_path / "linked" / "notebook.py"
        linked_notebook.parent.mkdir()
        (linked_notebook.parent / "__marimo__").symlink_to(outside_dir)
    except OSError:
        pytest.skip("symlinks are not available")

    exporter = AutoExporter()
    try:
        md = exporter.reserve_revision(str(notebook), "md")
        assert not await exporter.save_md(str(notebook), "new", revision=md)
        html = exporter.reserve_revision(str(notebook), "html")
        assert not await exporter.save_html(
            str(notebook), "new", revision=html
        )
        linked = exporter.reserve_revision(str(linked_notebook), "md")
        assert not await exporter.save_md(
            str(linked_notebook), "new", revision=linked
        )
    finally:
        exporter.cleanup()

    assert outside_file.read_text() == "original"
    assert not (tmp_path / "dangling.html").exists()
    assert list(outside_dir.iterdir()) == []
