# Copyright 2026 Marimo. All rights reserved.
"""CLI tests for the marimo cache command group."""

from __future__ import annotations

import json
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
        CacheManifest(
            notebook=os.path.relpath(notebook, cache_dir), nodes=nodes
        ).to_bytes()
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


CACHING_NOTEBOOK = """import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    epochs = 2
    return


@app.cell
def _(epochs, mo):
    with mo.persistent_cache("train"):
        model = epochs * 2
    return


@app.cell
def _():
    note = "old"
    return
"""

CACHING_CELLS = (
    "import marimo as mo",
    "epochs = 2",
    'with mo.persistent_cache("train"):\n    model = epochs * 2',
    'note = "old"',
)


async def run_notebook(
    notebook: Path, cache_dir: Path, exec_req: ExecReqProvider
) -> None:
    """Run the cells of CACHING_NOTEBOOK, caching into `cache_dir`."""
    from marimo._save.stores.file import FileStore
    from tests._runtime._helpers.factories import default_app_metadata
    from tests._runtime._helpers.session import mocked_kernel_session

    with mocked_kernel_session(
        app_metadata=default_app_metadata(filename=str(notebook))
    ) as tk:
        # Pin the store. The ambient config can cache somewhere else entirely.
        tk.ctx.cache.store = FileStore(save_path=str(cache_dir))
        await tk.kernel.run([exec_req.get(cell) for cell in CACHING_CELLS])
        assert not tk.kernel.stderr.messages


def path_hash_of(notebook: Path, name: str) -> str:
    """The digest that entries of the cell defining `name` sit under."""
    from marimo._ast.app import InternalApp
    from marimo._ast.load import load_app
    from marimo._save.hash import hash_cell_closure

    app = load_app(str(notebook))
    assert app is not None
    graph = InternalApp(app).graph
    (cell_id,) = [
        cell_id for cell_id, cell in graph.cells.items() if name in cell.defs
    ]
    return hash_cell_closure(cell_id, graph).hex()


async def test_prune_deletes_what_edited_code_cannot_produce_again(
    tmp_path: Path, exec_req: ExecReqProvider
) -> None:
    from marimo._save.manifest import manifest_name

    notebook = tmp_path / "nb.py"
    notebook.write_text(CACHING_NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    await run_notebook(notebook, cache_dir, exec_req)
    (entry,) = list((cache_dir / "train").iterdir())
    manifest = cache_dir / manifest_name(notebook)

    notebook.write_text(CACHING_NOTEBOOK.replace("epochs = 2", "epochs = 3"))
    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert not entry.exists()
    # The manifest outlives the records it held, and forgets them.
    assert manifest.exists()
    assert read_manifest(manifest) == {}


async def test_prune_keeps_an_entry_an_unrelated_edit_left_alone(
    tmp_path: Path, exec_req: ExecReqProvider
) -> None:
    """An entry an earlier run produced survives for as long as the code that
    produced it does, whichever branch the last run happened to take."""
    from marimo._save.manifest import manifest_name

    notebook = tmp_path / "nb.py"
    notebook.write_text(CACHING_NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    await run_notebook(notebook, cache_dir, exec_req)
    (entry,) = list((cache_dir / "train").iterdir())
    recorded = read_manifest(cache_dir / manifest_name(notebook))
    assert recorded

    notebook.write_text(
        CACHING_NOTEBOOK.replace('note = "old"', 'note = "new"')
    )
    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "Nothing to delete." in result.output
    assert entry.exists()
    assert read_manifest(cache_dir / manifest_name(notebook)) == recorded


def test_prune_takes_the_blobs_a_dead_entry_reads(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", "ab12")
    manifest = write_manifest(
        cache_dir, notebook, {"dead": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t30 B\t1 entry",
        "  1 record of code the notebook no longer has.",
        "Deleted 1 entry, freeing 30 B.",
    ]
    assert list((cache_dir / "train").iterdir()) == []
    assert read_manifest(manifest) == {}


def test_prune_keeps_an_entry_the_notebook_still_attests(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_entry(cache_dir, "train", "C_77e0.pickle", 10)
    live = path_hash_of(notebook, "x")
    manifest = write_manifest(
        cache_dir,
        notebook,
        {live: {"train": {"C_ab12"}}, "dead": {"train": {"C_77e0"}}},
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()
    assert not (cache_dir / "train" / "C_77e0.pickle").exists()
    assert read_manifest(manifest) == {live: {"train": {"C_ab12"}}}


def test_prune_keeps_an_entry_another_notebook_attests(tmp_path: Path) -> None:
    """Notebooks share a cache directory, and share what is in it."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    other = tmp_path / "other.py"
    other.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    write_manifest(
        cache_dir, other, {path_hash_of(other, "x"): {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_dry_run_deletes_nothing(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, notebook, {"dead": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(
        main, ["cache", "prune", str(notebook), "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t10 B\t1 entry",
        "  1 record of code the notebook no longer has.",
        "Deleted nothing (--dry-run).",
    ]
    assert (cache_dir / "train" / "C_ab12.pickle").exists()
    assert read_manifest(manifest) == {"dead": {"train": {"C_ab12"}}}


def test_prune_leaves_a_cache_nothing_records(tmp_path: Path) -> None:
    """A cache written before manifests existed is not one to guess about."""
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        "  Nothing records what wrote this cache, so nothing is pruned.",
        "Nothing to delete.",
    ]
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_keeps_an_entry_no_manifest_tracks(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_entry(cache_dir, "train", "C_77e0.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t10 B\t1 entry",
        "  1 record of code the notebook no longer has.",
        "  Kept 1 entry that no readable manifest tracks.",
        "Deleted 1 entry, freeing 10 B.",
    ]
    assert (cache_dir / "train" / "C_77e0.pickle").exists()


def test_prune_deletes_the_entries_of_a_deleted_notebook(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, tmp_path / "gone.py", {"3f9c": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()
    assert read_manifest(manifest) == {}


def test_prune_deletes_the_entries_of_an_emptied_notebook(
    tmp_path: Path,
) -> None:
    """A file left holding only a docstring has no cell that can produce an
    entry, so its records are as dead as a deleted notebook's."""
    notebook = tmp_path / "nb.py"
    notebook.write_text('"""Nothing left but this."""\n')
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()
    assert read_manifest(manifest) == {}


def test_prune_keeps_the_entries_of_a_notebook_that_does_not_compile(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "broken.py"
    notebook.write_text(
        "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _(:\n"
    )
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        "  broken.py does not read as a whole notebook, so its entries are kept.",
        "Nothing to delete.",
    ]
    assert (cache_dir / "train" / "C_ab12.pickle").exists()
    assert read_manifest(manifest) == {"3f9c": {"train": {"C_ab12"}}}


def test_prune_keeps_an_entry_a_notebook_that_does_not_compile_shares(
    tmp_path: Path,
) -> None:
    """One of the notebooks sharing a cache cannot be read for liveness, so
    what it recorded stays however dead another notebook's records are."""
    broken = tmp_path / "broken.py"
    broken.write_text(
        "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _(:\n"
    )
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, broken, {"3f9c": {"train": {"C_ab12"}}})
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "broken.py does not read as a whole notebook" in result.output
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_keeps_the_entries_of_a_manifest_that_moved(
    tmp_path: Path,
) -> None:
    """A manifest is named after where its notebook was. One that no longer
    answers to its own name says nothing about which source to compile."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, notebook, {"dead": {"train": {"C_ab12"}}}
    )
    moved = manifest.with_name(manifest.name.replace("nb-", "moved-"))
    manifest.rename(moved)

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert (
        f"{moved.name} does not say which notebook wrote it" in result.output
    )
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_keeps_an_entry_a_manifest_that_moved_shares(
    tmp_path: Path,
) -> None:
    """A record that cannot be attributed to a notebook is a record no source
    can be read against, and so one that keeps its entries alive."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    foreign = write_manifest(
        cache_dir, tmp_path / "other.py", {"3f9c": {"train": {"C_ab12"}}}
    )
    foreign.rename(foreign.with_name(foreign.name.replace("other-", "moved-")))

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "does not say which notebook wrote it" in result.output
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_leaves_the_files_that_are_not_cache_manifests(
    tmp_path: Path,
) -> None:
    """A cache directory holds other bookkeeping, such as the manifest an
    export writes, which records nothing about what wrote the cache."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, notebook, {"dead": {"train": {"C_ab12"}}}
    )
    export = cache_dir / ".nb-export.json"
    export.write_bytes(b"m" * 3)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t10 B\t1 entry",
        "  1 record of code the notebook no longer has.",
        "Deleted 1 entry, freeing 10 B.",
    ]
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()
    assert export.read_bytes() == b"m" * 3
    assert manifest.exists()


def unreadable_cache(
    tmp_path: Path, unreadable: bytes = b"{not json"
) -> tuple[Path, Path]:
    """A cache holding a dead entry beside a manifest that cannot be read."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    (cache_dir / "other-0123456789abcdef.json").write_bytes(unreadable)
    return notebook, cache_dir


def test_prune_skips_a_manifest_from_a_newer_marimo(tmp_path: Path) -> None:
    """A manifest this marimo cannot read can still list entries, so
    deleting them rests on another manifest's word alone."""
    from marimo._save.manifest import MANIFEST_VERSION

    payload = json.dumps(
        {"version": MANIFEST_VERSION + 1, "nodes": {}}
    ).encode()
    notebook, cache_dir = unreadable_cache(tmp_path, payload)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "written by a newer version" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_skips_an_unreadable_manifest_with_no_one_to_ask(
    tmp_path: Path,
) -> None:
    notebook, cache_dir = unreadable_cache(tmp_path)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "cannot be read" in result.output
    assert f"Skipping {cache_dir}" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_asks_before_acting_on_an_unreadable_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._cli.cache import commands

    monkeypatch.setattr(commands, "_interactive", lambda: True)
    notebook, cache_dir = unreadable_cache(tmp_path)

    refused = CliRunner().invoke(
        main, ["cache", "prune", str(notebook)], input="n\n"
    )

    assert refused.exit_code == 0, refused.output
    assert f"Delete 1 entry (10 B) from {cache_dir}?" in refused.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()

    accepted = CliRunner().invoke(
        main, ["cache", "prune", str(notebook)], input="y\n"
    )

    assert accepted.exit_code == 0, accepted.output
    assert "Deleted 1 entry, freeing 10 B." in accepted.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_reports_an_unreadable_manifest_it_did_not_hold_up(
    tmp_path: Path,
) -> None:
    """A manifest that cannot be read is worth knowing about before the edit
    that turns it into the thing standing between a prune and its entries."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(
        cache_dir,
        notebook,
        {path_hash_of(notebook, "x"): {"train": {"C_ab12"}}},
    )
    name = "other-0123456789abcdef.json"
    (cache_dir / name).write_bytes(b"{not json")

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert f"  {name} cannot be read" in result.output
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_asks_before_deleting_beside_an_empty_manifest(
    tmp_path: Path,
) -> None:
    """A manifest an interrupted write left empty lists nothing, so the
    notebook it was written for can still be reading what prune deletes."""
    from marimo._save.manifest import manifest_name

    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    sibling = tmp_path / "other.py"
    sibling.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    (cache_dir / manifest_name(sibling)).write_bytes(b"")

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert f"  {manifest_name(sibling)} holds no records." in result.output
    assert f"Skipping {cache_dir}" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_asks_before_deleting_beside_an_unattested_notebook(
    tmp_path: Path,
) -> None:
    """A notebook that never recorded what it cached can still be reading
    it."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    sibling = tmp_path / "other.py"
    sibling.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "  other.py shares this cache and has no manifest." in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()

    forced = CliRunner().invoke(
        main, ["cache", "prune", str(notebook), "--force"]
    )

    assert forced.exit_code == 0, forced.output
    assert "Deleted 1 entry, freeing 10 B." in forced.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_deletes_beside_a_file_that_is_not_a_notebook(
    tmp_path: Path,
) -> None:
    """A plain module shares the directory without sharing the cache."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    (tmp_path / "utils.py").write_text("print('hello')\n")
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "utils.py" not in result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_takes_the_answer_from_the_global_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._config.settings import GLOBAL_SETTINGS

    # Restored on teardown: the setting outlives the invocation that set it.
    monkeypatch.setattr(GLOBAL_SETTINGS, "YES", False)
    notebook, cache_dir = unreadable_cache(tmp_path)

    result = CliRunner().invoke(main, ["-y", "cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_yes_answers_the_prompt_like_force(tmp_path: Path) -> None:
    notebook, cache_dir = unreadable_cache(tmp_path)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_asks_when_a_cache_is_not_beside_its_notebooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under sys.pycache_prefix there is nowhere to look for the notebooks
    that share a cache, so prune cannot vouch for what it deletes."""
    prefix = tmp_path / "prefix"
    monkeypatch.setattr(sys, "pycache_prefix", str(prefix))
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = prefix.joinpath(*tmp_path.parts[1:]) / "__marimo__" / "cache"
    cache_dir.mkdir(parents=True)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])

    assert result.exit_code == 0, result.output
    assert "cannot be checked for a manifest" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


def test_prune_of_a_cache_directory_that_does_not_exist(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo import _loggers

    # marimo's logger does not propagate. Without this, caplog sees nothing.
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    cache_dir = tmp_path / "__marimo__" / "cache"
    assert result.output.splitlines() == [
        f"{cache_dir} (does not exist)\t0 B\t0 entries",
        "  Nothing records what wrote this cache, so nothing is pruned.",
        "Nothing to delete.",
    ]
    # A cache nothing wrote yet is the ordinary case, reported in the
    # output rather than logged as a directory that could not be read.
    assert str(cache_dir) not in caplog.text


def test_prune_recursive_reports_a_total(tmp_path: Path) -> None:
    dirs = []
    for name, key in (("a", "C_ab12"), ("b", "C_77e0")):
        notebook = tmp_path / name / "nb.py"
        notebook.parent.mkdir()
        notebook.write_text(NOTEBOOK)
        cache_dir = make_cache_dir(tmp_path, name)
        write_entry(cache_dir, "train", f"{key}.pickle", 1024)
        write_manifest(cache_dir, notebook, {"dead": {"train": {key}}})
        dirs.append(cache_dir)

    result = CliRunner().invoke(main, ["cache", "prune", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{dirs[0]}\t1.0 KB\t1 entry",
        "  1 record of code the notebook no longer has.",
        f"{dirs[1]}\t1.0 KB\t1 entry",
        "  1 record of code the notebook no longer has.",
        "Total\t2.0 KB\t2 entries",
        "Deleted 2 entries, freeing 2.0 KB.",
    ]


def test_prune_recursive_reports_no_cache_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["cache", "prune", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output == "No cache directories found.\n"


def test_prune_rejects_a_file_that_is_not_a_notebook(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text("print('hello')\n")

    result = CliRunner().invoke(main, ["cache", "prune", str(script)])

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


def test_apply_prune_keeps_an_entry_recorded_live_since_the_plan(
    tmp_path: Path,
) -> None:
    """A plan waits on a prompt. A kernel that records the doomed entry
    under live code in the meantime keeps it, record and all."""
    from marimo._save.prune import _live_nodes, apply_prune, plan_prune

    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    other = tmp_path / "other.py"
    other.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    live = _live_nodes(other)
    assert live
    node = next(iter(live))
    write_manifest(cache_dir, other, {node: {"train": {"C_77e0"}}})
    plan = plan_prune([cache_dir])
    assert plan.directories[0].entries == {("train", "C_ab12")}

    # The other notebook runs and records the doomed entry under live code.
    recorded = write_manifest(
        cache_dir, other, {node: {"train": {"C_ab12", "C_77e0"}}}
    )
    freed = apply_prune(plan)

    assert freed.entries == 0
    assert (cache_dir / "train" / "C_ab12.pickle").exists()
    assert ("train", "C_ab12") in {
        (block, key)
        for blocks in read_manifest(recorded).values()
        for block, keys in blocks.items()
        for key in keys
    }


def test_prune_keeps_the_entries_of_a_notebook_that_parses_with_errors(
    tmp_path: Path,
) -> None:
    """A parse with errors can leave out a cell Python would still run.
    What the notebook holds is then unknown, never empty."""
    from marimo._ast.load import get_notebook_status

    notebook = tmp_path / "nb.py"
    notebook.write_text(
        NOTEBOOK.replace(
            'if __name__ == "__main__":',
            "if True:\n    @app.cell\n    def _():\n        y = 2\n"
            '        return (y,)\n\n\nif __name__ == "__main__":',
        )
    )
    assert get_notebook_status(str(notebook)).status == "has_errors"
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    manifest = write_manifest(
        cache_dir, notebook, {"dead": {"train": {"C_ab12"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "does not read as a whole notebook" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()
    assert read_manifest(manifest) == {"dead": {"train": {"C_ab12"}}}


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_prune_asks_before_deleting_beside_a_file_it_cannot_read(
    tmp_path: Path,
) -> None:
    """A sibling that cannot be read may well be a notebook writing here."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    sibling = tmp_path / "other.py"
    sibling.write_text(NOTEBOOK)
    sibling.chmod(0o000)
    if os.access(sibling, os.R_OK):
        sibling.chmod(0o644)
        pytest.skip("chmod does not restrict reads for this user")
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})

    try:
        result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])
    finally:
        sibling.chmod(0o644)

    assert result.exit_code == 0, result.output
    assert "other.py shares this cache and cannot be read." in result.output
    assert f"Skipping {cache_dir}" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_prune_asks_before_deleting_beside_a_manifest_it_cannot_read(
    tmp_path: Path,
) -> None:
    from marimo._save.manifest import manifest_name

    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    sibling = tmp_path / "other.py"
    sibling.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)
    write_manifest(cache_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    locked = write_manifest(
        cache_dir, sibling, {"3f9c": {"train": {"C_77e0"}}}
    )
    locked.chmod(0o000)
    if os.access(locked, os.R_OK):
        locked.chmod(0o644)
        pytest.skip("chmod does not restrict reads for this user")

    try:
        result = CliRunner().invoke(main, ["cache", "prune", str(notebook)])
    finally:
        locked.chmod(0o644)

    assert result.exit_code == 0, result.output
    assert f"  {manifest_name(sibling)} cannot be read:" in result.output
    assert f"Skipping {cache_dir}" in result.output
    assert (cache_dir / "train" / "C_ab12.pickle").exists()
