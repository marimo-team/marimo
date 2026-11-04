# Copyright 2026 Marimo. All rights reserved.
"""CLI tests for the marimo cache command group."""

from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from marimo._cli.cache.commands import cache, format_bytes
from marimo._cli.cli import main

if TYPE_CHECKING:
    from collections.abc import Callable

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


def test_recursive_needs_a_directory(tmp_path: Path) -> None:
    # A notebook names one cache directory, so there is nothing to search.
    # Accepting -r anyway hides a PATH given by mistake.
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    make_cache_dir(tmp_path)

    result = CliRunner().invoke(main, ["cache", "dir", "-r", str(notebook)])

    assert result.exit_code == 2, result.output
    assert "-r/--recursive searches a directory" in result.output


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
    write_entry(first, "train", "C_ab12ab12ab12ab12ab12ab.pickle", 2048)
    second = make_cache_dir(tmp_path, "b")
    write_entry(second, "train", "C_77e077e077e077e077e077.pickle", 1024)
    write_entry(second, "train", "E_9f009f009f009f009f009f.pickle", 1024)

    result = CliRunner().invoke(main, ["cache", "size", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{first}\t2.0 KB\t1 entry",
        f"{second}\t2.0 KB\t2 entries",
        "Total\t4.0 KB\t3 entries",
    ]


def test_size_of_a_single_directory_omits_the_total(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12ab12ab12ab12ab12ab.pickle", 10)

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
    write_entry(cache_dir, "train", "C_ab12ab12ab12ab12ab12ab.pickle", 4)

    result = CliRunner().invoke(main, ["cache", "size", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\t4 B\t1 entry\n"


def test_size_recursive_reports_no_cache_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["cache", "size", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output == "No cache directories found.\n"


H = "ab12ab12ab12ab12ab12ab"
H2 = "77e077e077e077e077e077"
H3 = "9f009f009f009f009f009f"
GONE = "gonegonegonegonegonego"


def write_lazy_entry(cache_dir: Path, block: str, entry_hash: str) -> None:
    """Write a 10 B marker and the 20 B directory of blobs that it names."""
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


RECORD = {"3f9c": {"train": {f"C_{H}"}}}


def tracked_notebook(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A notebook beside a cache that holds one lazy entry, with its record.

    Returns the notebook, the cache directory, and the manifest.
    """
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", H)
    manifest = write_manifest(cache_dir, notebook, RECORD)
    return notebook, cache_dir, manifest


def interactive(monkeypatch: pytest.MonkeyPatch, answer: str) -> io.BytesIO:
    """Pretend a terminal is attached, so the command prompts instead of skipping."""
    stream = io.BytesIO(answer.encode("utf-8"))
    monkeypatch.setattr(stream, "isatty", lambda: True)
    return stream


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under `root` with its bytes, to prove nothing changed."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_clean_deletes_every_block(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_lazy_entry(cache_dir, "train", H)
    write_entry(cache_dir, "evaluate", f"E_{H3}.pickle", 5)
    (cache_dir / ".nb-export.json").write_bytes(b"m" * 3)

    result = CliRunner().invoke(main, ["cache", "clean", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t35 B\t2 entries",
        "Deleted 2 entries, freeing 35 B.",
    ]
    assert [path.name for path in cache_dir.iterdir()] == [".nb-export.json"]


@pytest.mark.parametrize(("answer", "deleted"), [("n", False), ("y", True)])
def test_clean_asks_before_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str, deleted: bool
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", f"C_{H}.pickle", 10)

    result = CliRunner().invoke(
        main,
        ["cache", "clean", str(tmp_path)],
        input=interactive(monkeypatch, f"{answer}\n"),
    )

    assert result.exit_code == 0, result.output
    assert "Delete 1 entry (10 B)?" in result.output
    assert ("Deleted 1 entry, freeing 10 B." in result.output) is deleted
    assert (cache_dir / "train").exists() is not deleted


def test_clean_skips_the_prompt_with_no_one_to_answer(tmp_path: Path) -> None:
    """A script that forgot `-y` loses nothing. A piped answer is not a
    person, so it is not read either."""
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", f"C_{H}.pickle", 10)

    result = CliRunner().invoke(
        main, ["cache", "clean", str(tmp_path)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert "Skipping 1 entry (10 B): rerun with -y to delete." in result.output
    assert "Deleted" not in result.output
    assert (cache_dir / "train" / f"C_{H}.pickle").exists()


def test_clean_takes_the_answer_from_the_global_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._config.settings import GLOBAL_SETTINGS

    # The setting outlives the invocation that set it, so monkeypatch restores it.
    monkeypatch.setattr(GLOBAL_SETTINGS, "YES", False)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", f"C_{H}.pickle", 10)

    result = CliRunner().invoke(main, ["-y", "cache", "clean", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train").exists()


def test_clean_keeps_the_blocks_it_was_not_named(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", f"C_{H}.pickle", 10)
    write_entry(cache_dir, "evaluate", f"E_{H3}.pickle", 5)

    result = CliRunner().invoke(
        main, ["cache", "clean", str(tmp_path), "train", "-y"]
    )

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 10 B." in result.output
    assert not (cache_dir / "train").exists()
    assert (cache_dir / "evaluate" / f"E_{H3}.pickle").exists()


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
    write_entry(first, "train", f"C_{H}.pickle", 1024)
    second = make_cache_dir(tmp_path, "b")
    write_entry(second, "train", f"C_{H2}.pickle", 1024)

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


@pytest.mark.parametrize("flags", [["--dry-run"], ["-y", "--dry-run"]])
def test_clean_dry_run_reports_what_the_real_run_frees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str]
) -> None:
    first = make_cache_dir(tmp_path, "a")
    write_lazy_entry(first, "train", H)
    write_entry(first, "evaluate", f"E_{H3}.pickle", 5)
    second = make_cache_dir(tmp_path, "b")
    write_entry(second, "train", f"C_{H2}.pickle", 1024)
    before = snapshot(tmp_path)

    # A terminal answers no, but a dry run asks nothing.
    dry = CliRunner().invoke(
        main,
        ["cache", "clean", "-r", str(tmp_path), *flags],
        input=interactive(monkeypatch, "n\n"),
    )

    assert dry.exit_code == 0, dry.output
    assert dry.output.splitlines() == [
        f"{first}\t35 B\t2 entries",
        f"{second}\t1.0 KB\t1 entry",
        "Total\t1.0 KB\t3 entries",
        "Would delete 3 entries, freeing 1.0 KB.",
    ]
    assert snapshot(tmp_path) == before

    real = CliRunner().invoke(
        main, ["cache", "clean", "-r", str(tmp_path), "-y"]
    )

    assert real.exit_code == 0, real.output
    assert real.output.splitlines() == [
        line.replace("Would delete", "Deleted")
        for line in dry.output.splitlines()
    ]
    assert not (first / "train").exists()
    assert not (second / "train").exists()


def test_clean_notebook_deletes_only_what_the_manifest_lists(
    tmp_path: Path,
) -> None:
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    write_lazy_entry(cache_dir, "train", H2)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t30 B\t1 entry",
        "Deleted 1 entry, freeing 30 B.",
    ]
    # An entry no manifest lists is not this command's to delete.
    assert (cache_dir / "train" / f"C_{H2}.jsonl").exists()
    assert (cache_dir / "train" / H2 / "return.pickle").exists()
    assert not (cache_dir / "train" / H).exists()
    assert read_manifest(manifest) == {}


def test_clean_notebook_asks_before_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Declining leaves the entry, and the record of it, exactly as found."""
    notebook, _cache_dir, _manifest = tracked_notebook(tmp_path)
    before = snapshot(tmp_path)

    result = CliRunner().invoke(
        main,
        ["cache", "clean", str(notebook)],
        input=interactive(monkeypatch, "n\n"),
    )

    assert result.exit_code == 0, result.output
    assert "Delete 1 entry (30 B)?" in result.output
    assert "Deleted" not in result.output
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("flag", "verb", "kept"),
    [("-y", "Forgot", {}), ("--dry-run", "Would forget", None)],
)
def test_clean_notebook_forgets_a_record_no_file_answers_to(
    tmp_path: Path, flag: str, verb: str, kept: dict | None
) -> None:
    """A record that matches no file holds nothing, so it goes without a
    prompt. A dry run only reports it."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    nodes = {"3f9c": {"train": {f"C_{GONE}"}}}
    manifest = write_manifest(cache_dir, notebook, nodes)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), flag])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        "Nothing to delete.",
        f"{verb} 1 entry the cache no longer holds.",
    ]
    assert read_manifest(manifest) == (nodes if kept is None else kept)


@pytest.mark.parametrize("has_cache_dir", [True, False])
def test_clean_notebook_without_a_manifest(
    tmp_path: Path, has_cache_dir: bool
) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    if has_cache_dir:
        make_cache_dir(tmp_path)
        write_entry(cache_dir, "train", f"C_{H}.pickle", 10)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook)])

    assert result.exit_code == 0, result.output
    shown = (
        str(cache_dir) if has_cache_dir else f"{cache_dir} (does not exist)"
    )
    assert result.output.splitlines() == [
        shown,
        f"Nothing is tracked for {notebook}.",
    ]
    assert (cache_dir / "train" / f"C_{H}.pickle").exists() is has_cache_dir


def _corrupt_manifest(cache_dir: Path, manifest: Path) -> Callable[[], None]:
    del cache_dir
    manifest.write_bytes(b"{not json")
    return lambda: None


def _seal_block(cache_dir: Path, manifest: Path) -> Callable[[], None]:
    del manifest
    if sys.platform == "win32":
        pytest.skip("chmod does not restrict reads on Windows")
    block = cache_dir / "train"
    block.chmod(0o000)
    if os.access(block, os.R_OK):
        block.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")
    return lambda: block.chmod(0o755)


def _link_block(cache_dir: Path, manifest: Path) -> Callable[[], None]:
    del manifest
    if sys.platform == "win32":
        pytest.skip("symlinks need a privileged user")
    block = cache_dir / "train"
    elsewhere = cache_dir.parent / "elsewhere"
    shutil.move(block, elsewhere)
    block.symlink_to(elsewhere, target_is_directory=True)
    return lambda: None


@pytest.mark.parametrize(
    ("damage", "flag", "message"),
    [
        (_corrupt_manifest, "-y", "Manifest is not JSON"),
        (_corrupt_manifest, "--dry-run", "Manifest is not JSON"),
        (_seal_block, "-y", "Permission denied"),
        (_link_block, "-y", "is a symbolic link"),
    ],
    ids=["corrupt", "corrupt-dry-run", "unlistable", "linked"],
)
def test_clean_notebook_refuses_when_the_plan_fails(
    tmp_path: Path,
    damage: Callable[[Path, Path], Callable[[], None]],
    flag: str,
    message: str,
) -> None:
    """The command stops before changing anything if the manifest cannot be
    read, or if a block cannot be listed or is a link."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    repair = damage(cache_dir, manifest)
    before = manifest.read_bytes()

    try:
        result = CliRunner().invoke(
            main, ["cache", "clean", str(notebook), flag]
        )
    finally:
        repair()

    assert result.exit_code == 1
    assert message in result.stderr
    assert manifest.read_bytes() == before
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()


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


def test_clean_notebook_keeps_the_record_of_a_marker_that_cannot_be_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The blobs go first. A marker that then cannot be removed keeps its
    record, and the command reports the failure."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    marker = cache_dir / "train" / f"E_{H}.jsonl"
    marker.write_bytes(b"shared")
    write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {f"C_{H}", f"E_{H}"}}}
    )
    unlink = Path.unlink

    def deny_marker(path: Path, missing_ok: bool = False) -> None:
        if path == marker:
            raise PermissionError("read-only marker")
        unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", deny_marker)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 1
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert "1 path was not cleaned" in result.stderr
    assert not (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert not (cache_dir / "train" / H).exists()
    assert marker.read_bytes() == b"shared"
    assert read_manifest(manifest) == {"3f9c": {"train": {f"E_{H}"}}}


def test_clean_notebook_can_retry_an_entry_whose_blobs_stayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed blob removal leaves the marker and the record in place, so
    the next clean deletes the entry."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", lambda *_args, **_kwargs: None)
        result = CliRunner().invoke(
            main, ["cache", "clean", str(notebook), "-y"]
        )

    assert result.exit_code == 1
    assert "Deleted 0 entries, freeing 0 B." in result.output
    assert "1 path was not cleaned" in result.stderr
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert read_manifest(manifest) == RECORD

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert not (cache_dir / "train" / H).exists()
    assert read_manifest(manifest) == {}


def test_clean_notebook_dry_run_leaves_the_manifest_alone(
    tmp_path: Path,
) -> None:
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    write_lazy_entry(cache_dir, "train", H2)
    before = snapshot(tmp_path)

    dry = CliRunner().invoke(
        main, ["cache", "clean", str(notebook), "--dry-run"]
    )

    assert dry.exit_code == 0, dry.output
    assert dry.output.splitlines() == [
        f"{cache_dir}\t30 B\t1 entry",
        "Would delete 1 entry, freeing 30 B.",
    ]
    # A dry run neither rewrites nor locks the manifest.
    assert snapshot(tmp_path) == before
    assert not manifest.with_name(f"{manifest.name}.lock").exists()

    real = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert real.exit_code == 0, real.output
    assert real.output.splitlines() == [
        line.replace("Would delete", "Deleted")
        for line in dry.output.splitlines()
    ]
    assert (cache_dir / "train" / f"C_{H2}.jsonl").exists()
    assert read_manifest(manifest) == {}


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need a privileged user"
)
def test_clean_refuses_a_linked_cache_dir(tmp_path: Path) -> None:
    other = make_cache_dir(tmp_path, "other")
    write_entry(other, "train", f"C_{H}.pickle", 10)
    project = tmp_path / "project"
    (project / "__marimo__").mkdir(parents=True)
    (project / "__marimo__" / "cache").symlink_to(
        other, target_is_directory=True
    )

    result = CliRunner().invoke(main, ["cache", "clean", str(project), "-y"])

    assert result.exit_code == 1
    assert "is a symbolic link" in result.stderr
    assert (other / "train" / f"C_{H}.pickle").exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_clean_exits_nonzero_when_a_block_cannot_be_listed(
    tmp_path: Path,
) -> None:
    """The entries that the command deleted are reported, and the failure
    is reported too, in the exit code."""
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", f"C_{H}.pickle", 5)
    sealed = cache_dir / "evaluate"
    write_entry(cache_dir, "evaluate", f"E_{H}.pickle", 7)
    sealed.chmod(0o000)
    if os.access(sealed, os.R_OK):
        sealed.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")

    try:
        result = CliRunner().invoke(
            main, ["cache", "clean", str(tmp_path), "-y"]
        )
    finally:
        sealed.chmod(0o755)

    assert result.exit_code == 1
    assert "Deleted 1 entry, freeing 5 B." in result.output
    assert "1 path was not cleaned" in result.stderr
    assert not (cache_dir / "train").exists()
    assert (sealed / f"E_{H}.pickle").exists()
