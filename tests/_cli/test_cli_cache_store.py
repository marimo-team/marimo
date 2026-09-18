# Copyright 2026 Marimo. All rights reserved.
"""The cache commands act on the store the configuration picks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from marimo._cli.cli import main
from tests._cli.test_cli_cache import (
    NOTEBOOK,
    make_cache_dir,
    read_manifest,
    write_entry,
    write_lazy_entry,
    write_manifest,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def configure_store(monkeypatch: pytest.MonkeyPatch, store_dir: Path) -> None:
    """Configure `store_dir` as the cache store, as marimo.toml would."""
    from marimo._save import stores
    from marimo._save.stores.file import FileStore

    monkeypatch.setattr(
        stores,
        "configured_cache_store",
        lambda current_path=None: FileStore(  # noqa: ARG005
            save_path=str(store_dir)
        ),
    )


def test_dir_prints_the_configured_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `cache.store` entry replaces resolution. The kernel writes there,
    so the commands act there."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    make_cache_dir(tmp_path)
    store_dir = tmp_path / "elsewhere"
    store_dir.mkdir()
    configure_store(monkeypatch, store_dir)

    result = CliRunner().invoke(main, ["cache", "dir", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{store_dir}\n"


def test_clean_notebook_acts_on_the_configured_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    decoy = make_cache_dir(tmp_path)
    write_entry(decoy, "train", "C_ab12.pickle", 10)
    store_dir = tmp_path / "elsewhere"
    write_lazy_entry(store_dir, "train", "ab12")
    manifest = write_manifest(
        store_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )
    configure_store(monkeypatch, store_dir)

    result = CliRunner().invoke(main, ["cache", "clean", str(notebook), "-y"])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert not (store_dir / "train" / "ab12").exists()
    assert read_manifest(manifest) == {}
    # The notebook-adjacent directory was not what the kernel wrote to.
    assert (decoy / "train" / "C_ab12.pickle").exists()


def test_prune_acts_on_the_configured_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured store does not sit beside the notebooks that write it,
    so a prune there needs the same agreement as any displaced cache."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    store_dir = tmp_path / "elsewhere"
    write_lazy_entry(store_dir, "train", "ab12")
    write_manifest(store_dir, notebook, {"dead": {"train": {"C_ab12"}}})
    configure_store(monkeypatch, store_dir)

    result = CliRunner().invoke(
        main, ["cache", "prune", str(notebook), "--force"]
    )

    assert result.exit_code == 0, result.output
    assert "cannot be checked for a manifest" in result.output
    assert "Deleted 1 entry, freeing 30 B." in result.output
    assert list((store_dir / "train").iterdir()) == []
