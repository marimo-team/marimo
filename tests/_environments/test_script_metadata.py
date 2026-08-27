# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import pytest

from marimo._environments import script_metadata
from marimo._environments.uv import UvNotFoundError, is_uv_available

HAS_UV = is_uv_available()

BLOCK_WITH_TOOL_TABLES = """\
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
#
# [tool.uv.sources]
# numpy = { path = "../numpy" }
#
# [tool.marimo.export]
# lock_kind = "resolved"
# ///
"""


def test_loads_returns_none_without_block() -> None:
    assert script_metadata.loads("print('hi')\n") is None


def test_loads_rejects_multiple_blocks() -> None:
    block = "# /// script\n# dependencies = []\n# ///\n"
    with pytest.raises(ValueError, match="Multiple"):
        script_metadata.loads(block + "\n" + block)


def test_dumps_round_trips_tool_tables() -> None:
    project = script_metadata.loads(BLOCK_WITH_TOOL_TABLES)
    assert project is not None
    assert project["tool"]["uv"]["sources"]["numpy"] == {"path": "../numpy"}
    assert script_metadata.loads(script_metadata.dumps(project)) == project


def test_replace_block_keeps_backslashes_literal() -> None:
    code = BLOCK_WITH_TOOL_TABLES + "\nimport marimo\n"
    block = (
        '# /// script\n# dependencies = ["pkg @ file://C:\\\\wheels"]\n# ///'
    )
    replaced = script_metadata.replace_block(code, block)
    assert "C:\\\\wheels" in replaced
    assert "import marimo" in replaced


def test_wrap_block() -> None:
    assert script_metadata.wrap_block('dependencies = ["numpy"]') == (
        '# /// script\n# dependencies = ["numpy"]\n# ///'
    )


@pytest.mark.parametrize(
    "error",
    [
        UvNotFoundError(),
        subprocess.TimeoutExpired(["uv", "add"], timeout=60),
    ],
)
def test_edit_normalizes_invocation_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    monkeypatch.setattr(script_metadata, "uv", fail)

    with pytest.raises(script_metadata.ScriptMetadataError) as exc_info:
        script_metadata.add_dependencies("notebook.py", ["idna"])

    assert exc_info.value.__cause__ is error
    assert str(error) in str(exc_info.value)


def test_failed_frontmatter_edit_preserves_notebook_and_removes_carrier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = """---
title: Test
pyproject: |
  dependencies = []
---

# Hello
"""
    notebook = tmp_path / "notebook.md"
    notebook.write_text(original)
    error = UvNotFoundError("uv disappeared")

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    monkeypatch.setattr(script_metadata, "uv", fail)

    with pytest.raises(script_metadata.ScriptMetadataError) as exc_info:
        script_metadata.add_dependencies(str(notebook), ["idna"])

    assert exc_info.value.__cause__ is error
    assert str(error) in str(exc_info.value)
    assert notebook.read_text() == original
    assert [path.name for path in tmp_path.iterdir()] == ["notebook.md"]


@pytest.mark.network
@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_ensure_marimo_adds_marimo(tmp_path: Path) -> None:
    script_path = tmp_path / "test.py"
    script_path.write_text(
        """# /// script
# dependencies = ["numpy"]
# ///
import marimo
"""
    )

    script_metadata.ensure_marimo(str(script_path))

    content = script_path.read_text()
    assert "marimo" in content
    assert "numpy" in content


def test_ensure_noop_when_present(tmp_path: Path) -> None:
    original = """# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo", "numpy"]
# ///
import marimo
"""
    script_path = tmp_path / "test.py"
    script_path.write_text(original)

    script_metadata.ensure_marimo(str(script_path))
    script_metadata.ensure_requires_python(str(script_path))

    assert script_path.read_text() == original


def test_ensure_marimo_noop_for_missing_or_empty_file(
    tmp_path: Path,
) -> None:
    script_metadata.ensure_marimo(str(tmp_path / "missing.py"))
    empty = tmp_path / "empty.py"
    empty.write_text("")
    script_metadata.ensure_marimo(str(empty))
    assert empty.read_text() == ""


@pytest.mark.network
@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_ensure_adds_when_no_metadata(tmp_path: Path) -> None:
    script_path = tmp_path / "test.py"
    script_path.write_text("import marimo\napp = marimo.App()\n")

    script_metadata.ensure_marimo(str(script_path))
    script_metadata.ensure_requires_python(str(script_path))

    content = script_path.read_text()
    assert "# /// script" in content
    assert "marimo" in content
    assert "requires-python" in content


def test_ensure_requires_python_only_touches_the_header(
    tmp_path: Path,
) -> None:
    """Regression test for #8054.

    The multi-line deps list must not be reformatted, and similar-looking
    text elsewhere in the file (e.g. docstrings) must not be modified.
    """
    original = '''# /// script
# dependencies = [
#     "polars",
#     "marimo>=0.8.0",
# ]
# ///
import marimo

app = marimo.App()

@app.cell
def __():
    """
    Example of PEP 723 metadata:

    # /// script
    # requires-python = ">=3.11"
    # ///
    """
    return ()
'''
    script_path = tmp_path / "test.py"
    script_path.write_text(original)

    script_metadata.ensure_requires_python(str(script_path))

    major, minor = platform.python_version_tuple()[:2]
    expected = original.replace(
        "# /// script\n",
        f'# /// script\n# requires-python = ">={major}.{minor}"\n',
        1,
    )
    assert script_path.read_text() == expected


@pytest.mark.network
@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_add_and_remove_dependencies(tmp_path: Path) -> None:
    script_path = tmp_path / "test.py"
    script_path.write_text(
        """# /// script
# dependencies = []
# ///
"""
    )

    script_metadata.add_dependencies(str(script_path), ["idna"])
    project = script_metadata.loads(script_path.read_text())
    assert project is not None
    assert any(dep.startswith("idna") for dep in project["dependencies"])

    script_metadata.remove_dependencies(str(script_path), ["idna"])
    project = script_metadata.loads(script_path.read_text())
    assert project is not None
    assert project["dependencies"] == []


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_frontmatter_edit_resolves_relative_sources(tmp_path: Path) -> None:
    """Relative `[tool.uv.sources]` paths resolve against the notebook's
    directory: the carrier lives next to the notebook, so uv anchors them
    natively and the round-trip leaves them untouched."""
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "mylib"\nversion = "0.1.0"\n'
    )
    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        """---
pyproject: |
  requires-python = ">=3.11"
  dependencies = []

  [tool.uv.sources]
  mylib = { path = "./lib" }
---

# Hello
"""
    )

    script_metadata.add_dependencies(str(notebook), ["mylib"])

    content = notebook.read_text()
    assert "mylib" in content
    assert 'path = "./lib"' in content
    # The carrier is deleted when the edit finishes.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["lib", "notebook.md"]


@pytest.mark.network
@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_add_dependencies_markdown_frontmatter(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        """---
title: Test
pyproject: |
  requires-python = ">=3.11"
  dependencies = []
---

# Hello
"""
    )

    script_metadata.add_dependencies(str(notebook), ["idna"])

    content = notebook.read_text()
    assert "idna" in content
    assert "# Hello" in content
    assert "title: Test" in content


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_edits_accept_relative_notebook_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """uv runs from the notebook's directory, so a relative target with a
    directory component must not be re-resolved against that directory."""
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    (notebooks / "nb.py").write_text(
        """# /// script
# dependencies = ["numpy"]
# ///
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    script_metadata.remove_dependencies("notebooks/nb.py", ["numpy"])

    project = script_metadata.loads((notebooks / "nb.py").read_text())
    assert project is not None
    assert project["dependencies"] == []


def test_materialize_python_notebook_is_itself(tmp_path: Path) -> None:
    script = tmp_path / "nb.py"
    script.write_text("# /// script\n# dependencies = []\n# ///\n")

    with script_metadata.materialized_for_environment(
        str(script)
    ) as materialized:
        assert materialized.path == str(script)
        assert materialized.directory == str(tmp_path)
    assert script.exists()


def test_materialize_markdown_carrier_is_adjacent_and_stable(
    tmp_path: Path,
) -> None:
    """The carrier sits next to the notebook under a versioned,
    deterministic name, carries the header verbatim, and is deleted on
    exit."""
    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        """---
pyproject: |
  dependencies = []

  [tool.uv.sources]
  mylib = { path = "./lib" }
---

# Hello
"""
    )

    with script_metadata.materialized_for_environment(str(notebook)) as first:
        assert first.directory == str(tmp_path)
        carrier = Path(first.path)
        assert carrier.parent == tmp_path
        assert carrier.name == ".marimo-v1-notebook.md.py"
        # The header is verbatim: relative paths are uv's to anchor.
        assert 'path = "./lib"' in carrier.read_text()
    assert not carrier.exists()

    with script_metadata.materialized_for_environment(str(notebook)) as second:
        assert second.path == first.path


def test_stranded_carriers_are_swept(tmp_path: Path) -> None:
    """A stray from a killed process is removed on the next operation;
    a fresh carrier (a concurrent process's) is spared."""
    import os as _os
    import time as _time

    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        "---\npyproject: |\n  dependencies = []\n---\n\n# Hi\n"
    )
    stale = tmp_path / ".marimo-v1-notebook.md.stranded.py"
    stale.write_text("# stray\n")
    old = _time.time() - 3600
    _os.utime(stale, (old, old))
    fresh = tmp_path / ".marimo-v1-notebook.md.inflight.py"
    fresh.write_text("# in flight\n")

    with script_metadata.materialized_for_environment(str(notebook)):
        pass

    assert not stale.exists()
    assert fresh.exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows ignores POSIX directory permissions",
)
def test_materialize_falls_back_when_directory_is_read_only(
    tmp_path: Path,
) -> None:
    """A read-only notebook directory materializes the carrier at a
    deterministic temp path instead of failing."""
    import os as _os
    import stat as _stat

    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        "---\npyproject: |\n  dependencies = []\n---\n\n# Hi\n"
    )
    _os.chmod(tmp_path, _stat.S_IRUSR | _stat.S_IXUSR)
    try:
        with script_metadata.materialized_for_environment(
            str(notebook)
        ) as first:
            assert Path(first.path).parent != tmp_path
            assert Path(first.path).exists()
            fallback = first.path
        with script_metadata.materialized_for_environment(
            str(notebook)
        ) as second:
            assert second.path == fallback
    finally:
        _os.chmod(tmp_path, 0o700)
