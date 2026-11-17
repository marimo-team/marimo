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
from marimo._save.cache_dirs import CacheDirStats

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
        CacheManifest(
            notebook=os.path.relpath(notebook, cache_dir), nodes=nodes
        ).to_bytes()
    )
    return path


def live_manifest(cache_dir: Path, root: Path) -> Path:
    """Record the entry `C_{H}` of block `train` as live for a notebook in
    `root`, so that `cache_dir` is a cache that prune manages."""
    notebook = root / "nb.py"
    notebook.write_text(NOTEBOOK)
    write_manifest(
        cache_dir,
        notebook,
        {path_hash_of(notebook, "x"): {"train": {f"C_{H}"}}},
    )
    return notebook


def write_orphan_blobs(cache_dir: Path, block: str, entry_hash: str) -> Path:
    """Write a 20 B directory of blobs with no marker to read it, as a kernel
    killed mid-write leaves one. A blank `block` writes at the cache root."""
    blobs = cache_dir / block / entry_hash
    blobs.mkdir(parents=True, exist_ok=True)
    (blobs / "return.pickle").write_bytes(b"y" * 20)
    return blobs


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

DEAD_NODE = "1 path hash of code the notebook no longer has."
NO_MANIFEST = "No manifest records this cache, so its entries are kept."
KEPT_WHOLE = "does not read as a whole notebook, so its entries are kept."
CLAIMED = (
    "(1) cache entries are locked. Either the entry is being written, or a "
    "notebook unexpectedly crashed while caching. Pass --force to remove them."
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


@pytest.mark.parametrize(
    ("old", "new", "deleted"),
    [
        ("epochs = 2", "epochs = 3", True),
        ('note = "old"', 'note = "new"', False),
    ],
    ids=["dependency", "unrelated"],
)
async def test_prune_deletes_what_edited_code_cannot_produce_again(
    tmp_path: Path,
    exec_req: ExecReqProvider,
    old: str,
    new: str,
    deleted: bool,
) -> None:
    """An entry lives as long as the code that produced it, whichever
    branch the last run took. An edit to a cell that the cached cell
    depends on makes its path hash dead."""
    from marimo._save.manifest import manifest_name

    notebook = tmp_path / "nb.py"
    notebook.write_text(CACHING_NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    await run_notebook(notebook, cache_dir, exec_req)
    (entry,) = (cache_dir / "train").glob("*.jsonl")
    manifest = cache_dir / manifest_name(notebook)
    recorded = read_manifest(manifest)
    assert recorded

    notebook.write_text(CACHING_NOTEBOOK.replace(old, new))
    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert entry.exists() is not deleted
    if deleted:
        assert DEAD_NODE in result.output
        assert "Deleted 1 entry" in result.output
        # The manifest outlives the records it held, and forgets them.
        assert read_manifest(manifest) == {}
    else:
        assert "Nothing to delete." in result.output
        assert read_manifest(manifest) == recorded


def test_prune_deletes_dead_entries_and_keeps_live_ones(
    tmp_path: Path,
) -> None:
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    write_entry(cache_dir, "train", f"C_{H2}.pickle", 10)
    live = path_hash_of(notebook, "x")
    write_manifest(
        cache_dir, notebook, {**RECORD, live: {"train": {f"C_{H2}"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t30 B\t1 entry",
        f"  {DEAD_NODE}",
        "Deleted 1 entry, freeing 30 B.",
    ]
    assert not (cache_dir / "train" / H).exists()
    assert not (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert (cache_dir / "train" / f"C_{H2}.pickle").exists()
    assert read_manifest(manifest) == {live: {"train": {f"C_{H2}"}}}


def test_prune_keeps_an_entry_another_notebook_records(tmp_path: Path) -> None:
    """Notebooks share a cache directory, and share what is in it. The
    record under the dead path hash stays with the entry it describes."""
    _notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    other = tmp_path / "other.py"
    other.write_text(NOTEBOOK)
    write_manifest(
        cache_dir, other, {path_hash_of(other, "x"): {"train": {f"C_{H}"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert read_manifest(manifest) == RECORD


def test_prune_removes_blob_directories_that_no_marker_reads(
    tmp_path: Path,
) -> None:
    """A kernel killed between the blobs and the marker leaves blobs that
    nothing can read. A directory with no entry beside it is left alone,
    because a store pointed at a project puts the project's own
    directories beside the blocks."""
    cache_dir = make_cache_dir(tmp_path)
    live_manifest(cache_dir, tmp_path)
    write_lazy_entry(cache_dir, "train", H)
    write_orphan_blobs(cache_dir, "train", H2)
    write_orphan_blobs(cache_dir, "evaluate", H3)

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t20 B\t1 entry",
        "Deleted 1 entry, freeing 20 B.",
    ]
    assert (cache_dir / "train" / H / "return.pickle").exists()
    assert not (cache_dir / "train" / H2).exists()
    assert (cache_dir / "evaluate" / H3 / "return.pickle").exists()


@pytest.mark.parametrize("shape", ["orphan", "first-write", "dead-entry"])
def test_prune_leaves_claimed_blob_directories_unless_forced(
    tmp_path: Path, shape: str
) -> None:
    """A lazy writer claims its blob directory with a partial marker before
    the first blob, so a prune that runs meanwhile leaves the blobs alone,
    whether the blobs are an orphan, the first write in a block, or a dead
    entry that is being rewritten. A writer that died leaves the claim
    behind, and `--force` sweeps both."""
    from marimo._save.cache_dirs import partial_write_name

    if shape == "dead-entry":
        notebook, cache_dir, _manifest = tracked_notebook(tmp_path)
        target, blobs, freed = notebook, cache_dir / "train" / H, "30 B"
        claim = cache_dir / "train" / partial_write_name(f"C_{H}.jsonl")
    else:
        cache_dir = make_cache_dir(tmp_path)
        live_manifest(cache_dir, tmp_path)
        if shape == "orphan":
            write_lazy_entry(cache_dir, "train", H)
        blobs = write_orphan_blobs(cache_dir, "train", H3)
        target, freed = tmp_path, "20 B"
        claim = cache_dir / "train" / partial_write_name(f"C_{H3}.jsonl")
    claim.write_bytes(b"")

    plain = CliRunner().invoke(main, ["cache", "prune", str(target), "-y"])

    assert plain.exit_code == 0, plain.output
    assert f"  {CLAIMED}" in plain.output
    assert "Nothing to delete." in plain.output
    assert (blobs / "return.pickle").exists()

    forced = CliRunner().invoke(
        main, ["cache", "prune", str(target), "--force", "-y"]
    )

    assert forced.exit_code == 0, forced.output
    assert f"Deleted 1 entry, freeing {freed}." in forced.output
    assert not blobs.exists()
    assert not claim.exists()


def test_prune_takes_root_blob_directories_only_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache named by stars alone writes at the root, beside the blocks,
    so a root directory is named in the report and deleted only when
    `--force` is given and the deletion is confirmed."""
    cache_dir = make_cache_dir(tmp_path)
    live_manifest(cache_dir, tmp_path)
    write_entry(cache_dir, "", f"C_{H}.pickle", 10)
    root = write_orphan_blobs(cache_dir, "", H3)

    plain = CliRunner().invoke(main, ["cache", "prune", str(tmp_path), "-y"])

    assert plain.exit_code == 0, plain.output
    assert "Nothing to delete." in plain.output
    assert H3 not in plain.output

    refused = CliRunner().invoke(
        main,
        ["cache", "prune", str(tmp_path), "--force"],
        input=interactive(monkeypatch, "n\n"),
    )

    assert refused.exit_code == 0, refused.output
    assert refused.output.splitlines()[:2] == [
        f"{cache_dir}\t20 B\t1 entry",
        f"  {H3} at the cache root holds blobs that no entry reads.",
    ]
    assert "Delete 1 entry (20 B)?" in refused.output
    assert (root / "return.pickle").exists()

    forced = CliRunner().invoke(
        main, ["cache", "prune", str(tmp_path), "--force", "-y"]
    )

    assert forced.exit_code == 0, forced.output
    assert "Deleted 1 entry, freeing 20 B." in forced.output
    assert not root.exists()
    assert cache_dir.is_dir()


def test_prune_removes_a_tracked_blob_directory_whose_marker_is_gone(
    tmp_path: Path,
) -> None:
    """A record of blobs with no marker describes nothing that a kernel can
    read, however live the code that produced it."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    (cache_dir / "train" / f"C_{H}.jsonl").unlink()
    write_lazy_entry(cache_dir, "train", H2)
    live = path_hash_of(notebook, "x")
    write_manifest(
        cache_dir, notebook, {live: {"train": {f"C_{H}", f"C_{H2}"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t20 B\t1 entry",
        "Deleted 1 entry, freeing 20 B.",
    ]
    assert not (cache_dir / "train" / H).exists()
    assert (cache_dir / "train" / H2 / "return.pickle").exists()
    assert read_manifest(manifest) == {live: {"train": {f"C_{H2}"}}}


def test_prune_dry_run_reports_what_the_real_run_frees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = tmp_path / "a" / "nb.py"
    notebook.parent.mkdir()
    notebook.write_text(NOTEBOOK)
    first = make_cache_dir(tmp_path, "a")
    write_lazy_entry(first, "train", H)
    write_entry(first, "train", f"C_{H2}.pickle", 10)
    manifest = write_manifest(
        first,
        notebook,
        {**RECORD, path_hash_of(notebook, "x"): {"train": {f"C_{H2}"}}},
    )
    second = make_cache_dir(tmp_path, "b")
    live_manifest(second, tmp_path / "b")
    write_lazy_entry(second, "train", H)
    write_orphan_blobs(second, "train", H3)
    before = snapshot(tmp_path)

    # A terminal answers no, but a dry run asks nothing.
    dry = CliRunner().invoke(
        main,
        ["cache", "prune", "-r", str(tmp_path), "--dry-run"],
        input=interactive(monkeypatch, "n\n"),
    )

    assert dry.exit_code == 0, dry.output
    assert dry.output.splitlines() == [
        f"{first}\t30 B\t1 entry",
        f"  {DEAD_NODE}",
        f"{second}\t20 B\t1 entry",
        "Total\t50 B\t2 entries",
        "Would delete 2 entries, freeing 50 B.",
    ]
    # A dry run neither rewrites nor locks the manifest.
    assert snapshot(tmp_path) == before
    assert not manifest.with_name(f"{manifest.name}.lock").exists()

    real = CliRunner().invoke(
        main, ["cache", "prune", "-r", str(tmp_path), "-y"]
    )

    assert real.exit_code == 0, real.output
    assert real.output.splitlines() == [
        line.replace("Would delete", "Deleted")
        for line in dry.output.splitlines()
    ]
    assert not (first / "train" / H).exists()
    assert (first / "train" / f"C_{H2}.pickle").exists()
    assert not (second / "train" / H3).exists()


@pytest.mark.parametrize(("answer", "deleted"), [("n", False), ("y", True)])
def test_prune_asks_before_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str, deleted: bool
) -> None:
    """Declining leaves the entry, and the record of it, exactly as found."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    before = manifest.read_bytes()

    result = CliRunner().invoke(
        main,
        ["cache", "prune", str(notebook)],
        input=interactive(monkeypatch, f"{answer}\n"),
    )

    assert result.exit_code == 0, result.output
    assert "Delete 1 entry (30 B)?" in result.output
    assert ("Deleted 1 entry, freeing 30 B." in result.output) is deleted
    assert (cache_dir / "train").exists() is not deleted
    assert (manifest.read_bytes() == before) is not deleted


def test_prune_skips_the_prompt_with_no_one_to_answer(tmp_path: Path) -> None:
    notebook, cache_dir, _manifest = tracked_notebook(tmp_path)

    result = CliRunner().invoke(
        main, ["cache", "prune", str(notebook)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert "Skipping 1 entry (30 B): rerun with -y to delete." in result.output
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()


def test_prune_leaves_a_cache_nothing_records(tmp_path: Path) -> None:
    """A cache written before manifests existed has no records to prune
    from, so nothing in it goes, blobs that no marker reads included.
    Entries that no manifest tracks are kept beside tracked ones."""
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", f"C_{H}.pickle", 10)
    orphan = write_orphan_blobs(cache_dir, "train", H3)

    result = CliRunner().invoke(
        main, ["cache", "prune", str(tmp_path), "--force", "-y"]
    )

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        f"  {NO_MANIFEST}",
        "Nothing to delete.",
    ]
    assert (cache_dir / "train" / f"C_{H}.pickle").exists()
    assert (orphan / "return.pickle").exists()
    shutil.rmtree(orphan)

    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    write_manifest(cache_dir, notebook, {"dead": {"train": {f"C_{H2}"}}})
    write_entry(cache_dir, "train", f"C_{H2}.pickle", 10)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t10 B\t1 entry",
        f"  {DEAD_NODE}",
        "  Kept 1 entry that no manifest tracks.",
        "Deleted 1 entry, freeing 10 B.",
    ]
    assert (cache_dir / "train" / f"C_{H}.pickle").exists()
    assert not (cache_dir / "train" / f"C_{H2}.pickle").exists()


@pytest.mark.parametrize(
    "source", [None, '"""Nothing left but this."""\n'], ids=["gone", "emptied"]
)
def test_prune_deletes_the_entries_of_a_notebook_with_no_cells(
    tmp_path: Path, source: str | None
) -> None:
    """A deleted notebook, or one left holding only a docstring, has no
    cell that can produce an entry, so every record of it is dead."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    if source is None:
        notebook.unlink()
    else:
        notebook.write_text(source)

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert not (cache_dir / "train").exists()
    assert read_manifest(manifest) == {}


BROKEN_NOTEBOOKS = {
    "syntax-error": (
        "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _(:\n"
    ),
    # A cell that parses but does not compile, such as one holding a bare
    # `break`, drops out of the compiled graph rather than raising.
    "uncompilable-cell": (
        "import marimo\n\napp = marimo.App()\n\n\n"
        "@app.cell\ndef _():\n    x = 1\n    return (x,)\n\n\n"
        "@app.cell\ndef _():\n    break\n    return\n"
    ),
    # A parse with errors can leave out a cell that Python still runs.
    "parse-errors": NOTEBOOK.replace(
        'if __name__ == "__main__":',
        "if True:\n    @app.cell\n    def _():\n        y = 2\n"
        '        return (y,)\n\n\nif __name__ == "__main__":',
    ),
}


@pytest.mark.parametrize(
    "source", list(BROKEN_NOTEBOOKS.values()), ids=list(BROKEN_NOTEBOOKS)
)
def test_prune_keeps_the_entries_of_a_notebook_it_cannot_read_whole(
    tmp_path: Path, source: str
) -> None:
    """What such a notebook holds is unknown, never empty, so its records
    stay, and so does any entry it shares with a notebook whose records
    are dead."""
    _notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    broken = tmp_path / "broken.py"
    broken.write_text(source)
    write_manifest(cache_dir, broken, {"3f9c": {"train": {f"C_{H}"}}})

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        f"  broken.py {KEPT_WHOLE}",
        f"  {DEAD_NODE}",
        "Nothing to delete.",
    ]
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert read_manifest(manifest) == RECORD


def test_prune_keeps_the_entries_of_a_manifest_that_moved(
    tmp_path: Path,
) -> None:
    """A manifest is named after the path of its notebook. One whose record
    no longer matches its own name does not say which source to compile."""
    _notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    moved = manifest.with_name(manifest.name.replace("nb-", "moved-"))
    manifest.rename(moved)

    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert (
        f"{moved.name} does not say which notebook wrote it" in result.output
    )
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{not json", "Manifest is not JSON"),
        (b'{"version": 99, "nodes": {}}', "written by a newer version"),
        (b"", "it holds no records"),
    ],
    ids=["corrupt", "newer", "empty"],
)
def test_prune_keeps_every_tracked_entry_beside_a_manifest_it_cannot_read(
    tmp_path: Path, payload: bytes, message: str
) -> None:
    """A manifest that cannot be read can still list entries under live
    code, so no tracked entry is deleted on the word of another manifest.
    Blobs that no marker reads are deleted all the same."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    write_orphan_blobs(cache_dir, "train", H2)
    (cache_dir / "other-0123456789abcdef.json").write_bytes(payload)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert (
        "  other-0123456789abcdef.json cannot be read, so every tracked "
        "entry is kept:" in result.output
    )
    assert message in result.output
    assert "Deleted 1 entry, freeing 20 B." in result.output
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert not (cache_dir / "train" / H2).exists()
    assert read_manifest(manifest) == RECORD


def test_prune_leaves_the_files_that_are_not_cache_manifests(
    tmp_path: Path,
) -> None:
    """A cache directory holds other bookkeeping, such as the manifest that
    an export writes, which records nothing about what wrote the cache."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    export = cache_dir / ".nb-export.json"
    export.write_bytes(b"m" * 3)

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert export.read_bytes() == b"m" * 3
    assert manifest.exists()


@pytest.mark.parametrize(
    ("flag", "verb"), [("--dry-run", "Would forget"), ("-y", "Forgot")]
)
def test_prune_forgets_a_record_no_file_answers_to(
    tmp_path: Path, flag: str, verb: str
) -> None:
    """A dead record of an entry that the cache no longer holds is forgotten
    without asking, because forgetting it removes no cached value."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    manifest = write_manifest(
        cache_dir, notebook, {"dead": {"train": {f"C_{GONE}"}}}
    )

    result = CliRunner().invoke(main, ["cache", "prune", str(notebook), flag])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{cache_dir}\t0 B\t0 entries",
        f"  {DEAD_NODE}",
        "Nothing to delete.",
        f"{verb} 1 entry the cache no longer holds.",
    ]
    assert (read_manifest(manifest) == {}) is (flag == "-y")


def test_prune_of_a_cache_directory_that_does_not_exist(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(main, ["cache", "prune", str(tmp_path)])

    assert result.exit_code == 0, result.output
    cache_dir = tmp_path / "__marimo__" / "cache"
    assert result.output.splitlines() == [
        f"{cache_dir} (does not exist)\t0 B\t0 entries",
        "Nothing to delete.",
    ]


def test_prune_recursive_continues_past_a_directory_that_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory that fails while the plan is applied is reported in the
    exit code, and the other directories are still pruned."""
    from marimo._save import prune

    dirs = []
    for name in ("a", "b"):
        notebook = tmp_path / name / "nb.py"
        notebook.parent.mkdir()
        notebook.write_text(NOTEBOOK)
        cache_dir = make_cache_dir(tmp_path, name)
        write_entry(cache_dir, "train", f"C_{H}.pickle", 1024)
        write_manifest(cache_dir, notebook, {"dead": {"train": {f"C_{H}"}}})
        dirs.append(cache_dir)
    apply_prune = prune.apply_prune

    def fail_first(plan: prune.PrunePlan) -> CacheDirStats:
        if plan.cache_dir == dirs[0]:
            raise OSError("disk went away")
        return apply_prune(plan)

    monkeypatch.setattr(prune, "apply_prune", fail_first)
    result = CliRunner().invoke(
        main, ["cache", "prune", "-r", str(tmp_path), "-y"]
    )

    assert result.exit_code == 1
    assert "Deleted 1 entry, freeing 1.0 KB." in result.output
    assert f"Skipping {dirs[0]}: disk went away" in result.stderr
    assert "1 path was not cleaned" in result.stderr
    assert (dirs[0] / "train" / f"C_{H}.pickle").exists()
    assert not (dirs[1] / "train").exists()


def test_prune_recursive_reports_a_total(tmp_path: Path) -> None:
    dirs = []
    for name, key in (("a", f"C_{H}"), ("b", f"C_{H2}")):
        notebook = tmp_path / name / "nb.py"
        notebook.parent.mkdir()
        notebook.write_text(NOTEBOOK)
        cache_dir = make_cache_dir(tmp_path, name)
        write_entry(cache_dir, "train", f"{key}.pickle", 1024)
        write_manifest(cache_dir, notebook, {"dead": {"train": {key}}})
        dirs.append(cache_dir)

    result = CliRunner().invoke(
        main, ["cache", "prune", "-r", str(tmp_path), "-y"]
    )

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{dirs[0]}\t1.0 KB\t1 entry",
        f"  {DEAD_NODE}",
        f"{dirs[1]}\t1.0 KB\t1 entry",
        f"  {DEAD_NODE}",
        "Total\t2.0 KB\t2 entries",
        "Deleted 2 entries, freeing 2.0 KB.",
    ]


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_prune_keeps_the_entries_of_a_notebook_it_cannot_reach(
    tmp_path: Path,
) -> None:
    """A notebook behind a directory that cannot be read is not a notebook
    that is gone, so its records are kept."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    nested = tmp_path / "private"
    nested.mkdir()
    moved = nested / "nb.py"
    notebook.rename(moved)
    write_manifest(cache_dir, moved, RECORD)
    manifest.unlink()
    nested.chmod(0o000)
    if os.access(moved, os.R_OK):
        nested.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")

    try:
        result = CliRunner().invoke(
            main, ["cache", "prune", str(tmp_path), "-y"]
        )
    finally:
        nested.chmod(0o755)

    assert result.exit_code == 0, result.output
    assert f"nb.py {KEPT_WHOLE}" in result.output
    assert "Nothing to delete." in result.output
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()


@pytest.mark.parametrize(
    ("damage", "message"),
    [(_seal_block, "Permission denied"), (_link_block, "is a symbolic link")],
    ids=["unlistable", "linked"],
)
def test_prune_refuses_when_the_plan_fails(
    tmp_path: Path,
    damage: Callable[[Path, Path], Callable[[], None]],
    message: str,
) -> None:
    """The command stops before changing anything if the block of a tracked
    entry cannot be listed or is a link."""
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    repair = damage(cache_dir, manifest)
    before = manifest.read_bytes()

    try:
        result = CliRunner().invoke(
            main, ["cache", "prune", str(notebook), "-y"]
        )
    finally:
        repair()

    assert result.exit_code == 1
    assert message in result.stderr
    assert manifest.read_bytes() == before
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
@pytest.mark.parametrize("sealed", ["root", "block", "blobs"])
def test_prune_exits_nonzero_when_a_path_cannot_be_listed(
    tmp_path: Path, sealed: str
) -> None:
    """What the command deleted is reported, and so is the failure, in the
    exit code. A cache root that cannot be listed is a failure too, never
    an empty plan."""
    cache_dir = make_cache_dir(tmp_path)
    live_manifest(cache_dir, tmp_path)
    write_lazy_entry(cache_dir, "train", H)
    write_orphan_blobs(cache_dir, "train", H2)
    write_lazy_entry(cache_dir, "evaluate", H)
    blobs = write_orphan_blobs(cache_dir, "evaluate", H3)
    target = {"root": cache_dir, "block": blobs.parent, "blobs": blobs}[sealed]
    target.chmod(0o000)
    if os.access(target, os.R_OK):
        target.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")

    try:
        result = CliRunner().invoke(
            main, ["cache", "prune", str(tmp_path), "-y"]
        )
    finally:
        target.chmod(0o755)

    assert result.exit_code == 1
    assert "1 path was not cleaned" in result.stderr
    if sealed == "root":
        assert "Nothing to delete." in result.output
        assert (cache_dir / "train" / H2 / "return.pickle").exists()
    else:
        assert "Deleted 1 entry, freeing 20 B." in result.output
        assert not (cache_dir / "train" / H2).exists()
    assert (blobs / "return.pickle").exists()
