# Copyright 2026 Marimo. All rights reserved.
"""CLI tests for the marimo cache command group."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from marimo._cli.cache.commands import cache, format_bytes
from marimo._cli.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import ExecReqProvider

NOTEBOOK = """
import marimo

app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
"""


def make_cache_dir(root: Path, *parts: str) -> Path:
    cache_dir = root.joinpath(*parts, "__marimo__", "cache")
    cache_dir.mkdir(parents=True)
    return cache_dir


def test_cache_group_is_registered_and_documented() -> None:
    # A hidden group drops out of `marimo --help` and out of the generated
    # CLI documentation.
    assert main.commands["cache"] is cache
    assert not cache.hidden


def test_dir_prints_the_directorys_own_cache_directory(tmp_path: Path) -> None:
    own = make_cache_dir(tmp_path)
    make_cache_dir(tmp_path, "nested")

    result = CliRunner().invoke(main, ["cache", "dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [str(own)]


def test_dir_recursive_prints_every_cache_directory(tmp_path: Path) -> None:
    first = make_cache_dir(tmp_path, "a")
    second = make_cache_dir(tmp_path, "b", "deeper")

    result = CliRunner().invoke(main, ["cache", "dir", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [str(first), str(second)]


def test_dir_defaults_to_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["cache", "dir"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [str(cache_dir)]


def test_dir_marks_a_cache_directory_that_does_not_exist(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(main, ["cache", "dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    expected = tmp_path / "__marimo__" / "cache"
    assert result.output == f"{expected} (does not exist)\n"


def test_dir_recursive_reports_no_cache_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main, ["cache", "dir", "--recursive", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert result.output == "No cache directories found.\n"


def test_dir_notebook_path(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    cache_dir.mkdir(parents=True)

    result = CliRunner().invoke(main, ["cache", "dir", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\n"


def test_dir_recursive_notebook_path(tmp_path: Path) -> None:
    # A notebook names one cache directory, so there is nothing to search and
    # -r neither errors nor changes the answer.
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    make_cache_dir(tmp_path, "nested")

    result = CliRunner().invoke(main, ["cache", "dir", "-r", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\n"


def test_dir_notebook_without_a_cache_directory(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)

    result = CliRunner().invoke(main, ["cache", "dir", str(notebook)])

    assert result.exit_code == 0, result.output
    expected = tmp_path / "__marimo__" / "cache"
    assert result.output == f"{expected} (does not exist)\n"


def test_dir_rejects_a_file_that_is_not_a_notebook(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text("print('hello')\n")

    result = CliRunner().invoke(main, ["cache", "dir", str(script)])

    assert result.exit_code == 1
    assert "is not a marimo notebook" in result.stderr


def test_dir_rejects_a_missing_path(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main, ["cache", "dir", str(tmp_path / "absent")]
    )

    assert result.exit_code == 2
    assert "does not exist" in result.stderr


def test_dir_marks_a_file_in_the_way_of_the_cache_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / "__marimo__").mkdir()
    blocker = tmp_path / "__marimo__" / "cache"
    blocker.write_text("")

    result = CliRunner().invoke(main, ["cache", "dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{blocker} (not a directory)\n"


def write_entry(cache_dir: Path, block: str, name: str, size: int) -> None:
    entry = cache_dir / block / name
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_bytes(b"x" * size)


@pytest.mark.parametrize(
    ("size", "rendered"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        # A byte short of the next unit rounds up to it, never to "1024.0".
        (1024**2 - 1, "1.0 MB"),
        (1024**3 - 1, "1.0 GB"),
        (3 * 1024 * 1024, "3.0 MB"),
        (1024**5, "1.0 PB"),
        # Nothing bigger than a petabyte to fall back on.
        (2 * 1024**6, "2048.0 PB"),
    ],
)
def test_format_bytes(size: int, rendered: str) -> None:
    assert format_bytes(size) == rendered


def test_size_reports_each_directory_and_a_total(tmp_path: Path) -> None:
    first = make_cache_dir(tmp_path, "a")
    write_entry(first, "train", "C_ab12.pickle", 2048)
    second = make_cache_dir(tmp_path, "b")
    write_entry(second, "train", "C_77e0.pickle", 1024)
    write_entry(second, "train", "E_9f00.pickle", 1024)

    result = CliRunner().invoke(main, ["cache", "size", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{first}\t2.0 KB\t1 entry",
        f"{second}\t2.0 KB\t2 entries",
        "Total\t4.0 KB\t3 entries",
    ]


def test_size_of_a_single_directory_omits_the_total(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(main, ["cache", "size", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [f"{cache_dir}\t10 B\t1 entry"]


def test_size_of_a_cache_directory_that_does_not_exist(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["cache", "size", str(tmp_path)])

    assert result.exit_code == 0, result.output
    expected = tmp_path / "__marimo__" / "cache"
    assert result.output == f"{expected} (does not exist)\t0 B\t0 entries\n"


def test_size_of_a_notebook_path(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 4)

    result = CliRunner().invoke(main, ["cache", "size", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\t4 B\t1 entry\n"


def test_size_recursive_reports_no_cache_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["cache", "size", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output == "No cache directories found.\n"


def write_lazy_entry(cache_dir: Path, block: str, entry_hash: str) -> None:
    """Write an entry and the directory of blobs it reads its value from."""
    blobs = cache_dir / block / entry_hash
    blobs.mkdir(parents=True, exist_ok=True)
    (blobs / "return.pickle").write_bytes(b"y" * 20)
    (cache_dir / block / f"C_{entry_hash}.jsonl").write_bytes(b"x" * 10)


def write_manifest(
    cache_dir: Path, notebook: Path, nodes: dict[str, dict[str, set[str]]]
) -> Path:
    from marimo._save.manifest import CacheManifest, manifest_name

    path = cache_dir / manifest_name(notebook)
    path.write_bytes(
        CacheManifest(notebook="../../nb.py", nodes=nodes).to_bytes()
    )
    return path


def read_manifest(path: Path) -> dict[str, dict[str, set[str]]]:
    from marimo._save.manifest import CacheManifest

    return CacheManifest.from_bytes(path.read_bytes()).nodes


def test_clean_deletes_every_block(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", "ab12")
    write_entry(cache_dir, "evaluate", "E_9f00.pickle", 5)
    (cache_dir / ".nb-export.json").write_bytes(b"m" * 3)

    result = CliRunner().invoke(main, ["cache", "clean", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t35 B\t2 entries",
        "Deleted 2 entries, freeing 35 B.",
    ]
    assert [path.name for path in cache_dir.iterdir()] == [".nb-export.json"]


def test_clean_asks_before_deleting(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(
        main, ["cache", "clean", str(tmp_path)], input="n\n"
    )

    assert result.exit_code == 0, result.output
    assert "Delete 1 entry (10 B)?" in result.output
    assert "Deleted" not in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_clean_deletes_once_confirmed(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(
        main, ["cache", "clean", str(tmp_path)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train").exists()


def test_clean_keeps_the_blocks_it_was_not_named(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_entry(cache_dir, "evaluate", "E_9f00.pickle", 5)

    result = CliRunner().invoke(
        main, ["cache", "clean", str(tmp_path), "train", "-y"]
    )

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train").exists()
    assert (cache_dir / "evaluate" / "E_9f00.pickle").exists()


def test_clean_of_a_cache_that_holds_nothing(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)

    result = CliRunner().invoke(main, ["cache", "clean", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        "Nothing to delete.",
    ]


def test_clean_recursive_reports_a_total(tmp_path: Path) -> None:
    first = make_cache_dir(tmp_path, "a")
    write_entry(first, "train", "C_ab12.pickle", 1024)
    second = make_cache_dir(tmp_path, "b")
    write_entry(second, "train", "C_77e0.pickle", 1024)

    result = CliRunner().invoke(
        main, ["cache", "clean", "-r", str(tmp_path), "-y"]
    )

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{first}\t1.0 KB\t1 entry",
        f"{second}\t1.0 KB\t1 entry",
        "Total\t2.0 KB\t2 entries",
        "Deleted 2 entries, freeing 2.0 KB.",
    ]
    assert not (first / "train").exists()
    assert not (second / "train").exists()


def test_clean_notebook_deletes_only_what_the_manifest_lists(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", "ab12")
    write_lazy_entry(cache_dir, "train", "77e0")
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t30 B\t1 entry",
        "Deleted 1 entry, freeing 30 B.",
    ]
    # An entry no manifest lists is not this command's to delete.
    assert (cache_dir / "train" / "C_77e0.jsonl").exists()
    assert (cache_dir / "train" / "77e0" / "return.pickle").exists()
    assert not (cache_dir / "train" / "ab12").exists()
    assert read_manifest(manifest) == {}


def test_clean_notebook_keeps_the_blocks_it_was_not_named(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", "ab12")
    write_lazy_entry(cache_dir, "evaluate", "77e0")
    manifest = write_manifest(
        cache_dir,
        notebook,
        {"3f9c": {"train": {"C_ab12"}, "evaluate": {"C_77e0"}}},
    )

    result = CliRunner().invoke(
        main, ["cache", "clean", str(notebook), "train", "-y"]
    )

    assert result.exit_code == 0, result.output
    assert not (cache_dir / "train" / "ab12").exists()
    assert (cache_dir / "evaluate" / "C_77e0.jsonl").exists()
    assert read_manifest(manifest) == {"3f9c": {"evaluate": {"C_77e0"}}}


def test_clean_notebook_matches_a_name_as_it_is_written_to_disk(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train_v2", "ab12")
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train_v2": {"C_ab12"}}}
    )

    result = CliRunner().invoke(
        main, ["cache", "clean", str(notebook), "train/v2", "-y"]
    )

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert not (cache_dir / "train_v2" / "ab12").exists()
    assert read_manifest(manifest) == {}


def test_clean_notebook_forgets_a_record_no_file_answers_to(
    tmp_path: Path,
) -> None:
    """A record no file answers to holds nothing, so it goes."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_gone"}}}
    )

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        "Nothing to delete.",
        "Forgot 1 entry the cache no longer holds.",
    ]
    assert read_manifest(manifest) == {}


def test_clean_notebook_refuses_a_record_that_leaves_the_cache(
    tmp_path: Path,
) -> None:
    """A manifest can be written by anything. It names entries or nothing."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    outside = tmp_path / "model.bin"
    outside.write_bytes(b"o" * 8)
    cache_dir = make_cache_dir(tmp_path)
    write_manifest(cache_dir, notebook, {"3f9c": {"../..": {"model"}}})

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert "Deleted" not in result.output
    assert outside.read_bytes() == b"o" * 8
    assert cache_dir.is_dir()


def test_clean_takes_the_answer_from_the_global_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._config.settings import GLOBAL_SETTINGS

    # Restored on teardown: the setting outlives the invocation that set it.
    monkeypatch.setattr(GLOBAL_SETTINGS, "YES", False)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(main, ["-y", "cache", "clean", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train").exists()


def test_clean_notebook_without_a_manifest(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        str(cache_dir),
        f"Nothing is tracked for {notebook}.",
    ]
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_clean_notebook_without_a_cache_directory(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook)])

    assert result.exit_code == 0, result.output
    cache_dir = tmp_path / "__marimo__" / "cache"
    assert result.output.splitlines() == [
        f"{cache_dir} (does not exist)",
        f"Nothing is tracked for {notebook}.",
    ]
    assert not cache_dir.exists()


def test_clean_notebook_refuses_an_unreadable_manifest(tmp_path: Path) -> None:
    from marimo._save.manifest import manifest_name

    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    (cache_dir / manifest_name(notebook)).write_bytes(b"{not json")

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 1
    assert "Manifest is not JSON" in result.stderr
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


async def test_clean_notebook_deletes_what_a_session_recorded(
    tmp_path: Path, exec_req: ExecReqProvider
) -> None:
    """What a run records is what a clean of that notebook deletes."""
    from marimo._save.manifest import manifest_name
    from marimo._save.stores.file import FileStore
    from tests._runtime._helpers.factories import default_app_metadata
    from tests._runtime._helpers.session import mocked_kernel_session

    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    with mocked_kernel_session(
        app_metadata=default_app_metadata(filename=str(notebook))
    ) as tk:
        # Pin the store. The ambient config can cache somewhere else entirely.
        tk.ctx.cache.store = FileStore(save_path=str(cache_dir))
        await tk.kernel.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("with mo.persistent_cache('train'):\n    x = 42"),
            ]
        )
    manifest = cache_dir / manifest_name(notebook)
    assert manifest.exists()
    assert list((cache_dir / "train").iterdir())

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert list((cache_dir / "train").iterdir()) == []
    assert read_manifest(manifest) == {}


def test_clean_rejects_a_file_that_is_not_a_notebook(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text("print('hello')\n")

    result = CliRunner().invoke(main, ["cache", "clean", str(script), "-y"])

    assert result.exit_code == 1
    assert "is not a marimo notebook" in result.stderr


def test_clean_notebook_matches_a_starred_name(tmp_path: Path) -> None:
    """`mo.persistent_cache("*train*")` writes to `train`. The name given
    to the command is matched the same way."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", "ab12")
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(
        main, ["cache", "clean", str(notebook), "*train*", "-y"]
    )

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert read_manifest(manifest) == {}


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict writes on Windows"
)
def test_clean_notebook_keeps_the_record_of_an_entry_that_stayed(
    tmp_path: Path,
) -> None:
    """An entry that could not be removed is still there to be read, and
    to be deleted another time, so its record stays with it."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", "ab12")
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )
    block = cache_dir / "train"
    block.chmod(0o555)
    if os.getuid() == 0:
        block.chmod(0o755)
        pytest.skip("chmod does not restrict writes for this user")

    try:
        result = CliRunner().invoke(
            main, ["cache", "clean", str(notebook), "-y"]
        )
    finally:
        block.chmod(0o755)

    assert result.exit_code == 0, result.output
    assert (block / "C_ab12.jsonl").exists()
    assert read_manifest(manifest) == {"3f9c": {"train": {"C_ab12"}}}
