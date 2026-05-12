from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._utils.inline_script_metadata import (
    PyProjectReader,
    _pyproject_toml_to_requirements_txt,
    has_marimo_in_script_metadata,
    is_marimo_dependency,
    script_metadata_hash_from_filename,
)
from marimo._utils.platform import is_windows
from marimo._utils.scripts import read_pyproject_from_script

if TYPE_CHECKING:
    from pathlib import Path


def test_get_dependencies():
    SCRIPT = """
# Copyright 2026 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "polars",
#     "marimo>=0.8.0",
#     "quak",
#     "vega-datasets",
# ]
# ///

import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")
"""
    assert PyProjectReader.from_script(SCRIPT).dependencies == [
        "polars",
        "marimo>=0.8.0",
        "quak",
        "vega-datasets",
    ]


def test_get_dependencies_github():
    url = "https://github.com/marimo-team/marimo/blob/a1e1be3190023a86650904249f911b2e6ffb8fac/examples/third_party/leafmap/leafmap_example.py"
    assert PyProjectReader.from_filename(url).dependencies == [
        "leafmap==0.41.0",
        "marimo",
    ]


def test_no_dependencies():
    SCRIPT = """
import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")
"""
    assert PyProjectReader.from_script(SCRIPT).dependencies == []


def test_windows_line_endings_from_url():
    """Test that script metadata from URL with Windows line endings is parsed correctly."""
    from unittest.mock import patch

    from marimo._utils.requests import Response

    # Script content as it would come from a Windows server with CRLF line endings
    SCRIPT_WITH_CRLF = b"""# /// script\r
# requires-python = ">=3.11"\r
# dependencies = [\r
#     "polars",\r
#     "marimo>=0.8.0",\r
# ]\r
# ///\r
\r
import marimo\r
\r
__generated_with = "0.8.2"\r
app = marimo.App(width="medium")\r
"""

    url = "https://example.com/notebook.py"

    with patch("marimo._utils.requests.get") as mock_get:
        # Mock the response to return content with Windows line endings
        mock_get.return_value = Response(
            200,
            SCRIPT_WITH_CRLF,
            {},
        )

        # This should now work correctly with the line ending normalization in response.text()
        reader = PyProjectReader.from_filename(url)
        assert reader.dependencies == ["polars", "marimo>=0.8.0"]
        assert reader.python_version == ">=3.11"


def test_pyproject_toml_to_requirements_txt_git_sources():
    pyproject = {
        "dependencies": [
            "marimo",
            "numpy",
            "polars",
            "altair",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "git": "https://github.com/marimo-team/marimo.git",
                        "rev": "main",
                    },
                    "numpy": {
                        "git": "https://github.com/numpy/numpy.git",
                        "branch": "main",
                    },
                    "polars": {
                        "git": "https://github.com/pola/polars.git",
                        "branch": "dev",
                    },
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ git+https://github.com/marimo-team/marimo.git@main",
        "numpy @ git+https://github.com/numpy/numpy.git@main",
        "polars @ git+https://github.com/pola/polars.git@dev",
        "altair",
    ]


def test_pyproject_toml_to_requirements_txt_with_marker():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "git": "https://github.com/marimo-team/marimo.git",
                        "tag": "0.1.0",
                        "marker": "python_version >= '3.12'",
                    }
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ git+https://github.com/marimo-team/marimo.git@0.1.0; python_version >= '3.12'",
        "polars",
    ]


def test_pyproject_toml_to_requirements_txt_with_url_sources():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "url": "https://github.com/marimo-team/marimo/archive/refs/heads/main.zip",
                    }
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ https://github.com/marimo-team/marimo/archive/refs/heads/main.zip",
        "polars",
    ]


@pytest.mark.skipif(is_windows(), reason="only testing posix paths")
def test_pyproject_toml_to_requirements_txt_with_local_path():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "path": "/Users/me/work/marimo",
                    }
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ /Users/me/work/marimo",
        "polars",
    ]


@pytest.mark.skipif(is_windows(), reason="only testing posix paths")
def test_pyproject_toml_to_requirements_txt_with_relative_path():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "path": "../local/marimo",
                    }
                }
            }
        },
    }
    # Test with a config path to verify relative path resolution
    config_path = "/Users/me/project/script.py"
    assert _pyproject_toml_to_requirements_txt(pyproject, config_path) == [
        "marimo @ /Users/me/local/marimo",
        "polars",
    ]


@pytest.mark.parametrize(
    "version_spec",
    [
        "marimo>=0.1.0",
        "marimo==0.1.0",
        "marimo<=0.1.0",
        "marimo>0.1.0",
        "marimo<0.1.0",
        "marimo~=0.1.0",
    ],
)
def test_pyproject_toml_to_requirements_txt_with_versioned_dependencies(
    version_spec: str,
):
    pyproject = {
        "dependencies": [
            version_spec,
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "git": "https://github.com/marimo-team/marimo.git",
                        "rev": "main",
                    },
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ git+https://github.com/marimo-team/marimo.git@main",
    ]


def test_get_python_version_requirement():
    pyproject = {"requires-python": ">=3.11"}
    assert (
        PyProjectReader(pyproject, config_path=None).python_version == ">=3.11"
    )

    pyproject = {"dependencies": ["polars"]}
    assert PyProjectReader(pyproject, config_path=None).python_version is None

    assert PyProjectReader({}, config_path=None).python_version is None

    pyproject = {"requires-python": {"invalid": "type"}}
    assert PyProjectReader(pyproject, config_path=None).python_version is None


def test_get_dependencies_with_python_version():
    SCRIPT = """
# /// script
# requires-python = ">=3.11"
# dependencies = ["polars"]
# ///

import marimo
"""
    assert PyProjectReader.from_script(SCRIPT).dependencies == ["polars"]

    pyproject = read_pyproject_from_script(SCRIPT)
    assert pyproject is not None
    assert (
        PyProjectReader(pyproject, config_path=None).python_version == ">=3.11"
    )

    SCRIPT_NO_PYTHON = """
# /// script
# dependencies = ["polars"]
# ///

import marimo
"""
    pyproject_no_python = read_pyproject_from_script(SCRIPT_NO_PYTHON)
    assert pyproject_no_python is not None
    assert (
        PyProjectReader(pyproject_no_python, config_path=None).python_version
        is None
    )
    assert PyProjectReader.from_script(SCRIPT_NO_PYTHON).dependencies == [
        "polars"
    ]


def test_get_dependencies_with_nonexistent_file():
    # Test with a non-existent file
    assert (
        PyProjectReader.from_filename("nonexistent_file.py").dependencies == []
    )

    # Test with empty
    assert PyProjectReader.from_filename("").dependencies == []


def test_is_marimo_dependency():
    assert is_marimo_dependency("marimo")
    assert is_marimo_dependency("marimo[extras]")
    assert not is_marimo_dependency("marimo-extras")
    assert not is_marimo_dependency("marimo-ai")

    # With version specifiers
    assert is_marimo_dependency("marimo==0.1.0")
    assert is_marimo_dependency("marimo[extras]>=0.1.0")
    assert is_marimo_dependency("marimo[extras]==0.1.0")
    assert is_marimo_dependency("marimo[extras]~=0.1.0")
    assert is_marimo_dependency("marimo[extras]<=0.1.0")
    assert is_marimo_dependency("marimo[extras]>=0.1.0")
    assert is_marimo_dependency("marimo[extras]<=0.1.0")

    # With other packages
    assert not is_marimo_dependency("numpy")
    assert not is_marimo_dependency("pandas")
    assert not is_marimo_dependency("marimo-ai")
    assert not is_marimo_dependency("marimo-ai==0.1.0")


def test_has_marimo_in_script_metadata(tmp_path):
    """Test has_marimo_in_script_metadata returns correct values."""
    # True: marimo present
    with_marimo = tmp_path / "with_marimo.py"
    with_marimo.write_text(
        "# /// script\n# dependencies = ['marimo']\n# ///\n"
    )
    assert has_marimo_in_script_metadata(str(with_marimo)) is True

    # False: metadata exists but no marimo
    without_marimo = tmp_path / "without_marimo.py"
    without_marimo.write_text(
        "# /// script\n# dependencies = ['numpy']\n# ///\n"
    )
    assert has_marimo_in_script_metadata(str(without_marimo)) is False

    # None: no metadata
    no_metadata = tmp_path / "no_metadata.py"
    no_metadata.write_text("import marimo\n")
    assert has_marimo_in_script_metadata(str(no_metadata)) is None

    # None: non-.py file
    assert has_marimo_in_script_metadata(str(tmp_path / "test.md")) is None


def test_script_metadata_hash_from_filename_none_without_metadata(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "no_metadata.py"
    notebook.write_text("import marimo\n", encoding="utf-8")
    assert script_metadata_hash_from_filename(str(notebook)) is None


def test_script_metadata_hash_from_filename_ignores_formatting(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    first.write_text(
        """
# /// script
# dependencies = [
#   "numpy",
#   "marimo>=0.20.0",
# ]
# requires-python = ">=3.11"
# ///
""",
        encoding="utf-8",
    )
    second = tmp_path / "second.py"
    second.write_text(
        """
# /// script
# requires-python   =   ">=3.11"
# dependencies = ["numpy", "marimo>=0.20.0"]
# ///
""",
        encoding="utf-8",
    )
    assert script_metadata_hash_from_filename(
        str(first)
    ) == script_metadata_hash_from_filename(str(second))


def test_script_metadata_hash_from_filename_changes_with_dependencies(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    first.write_text(
        """
# /// script
# dependencies = ["numpy"]
# ///
""",
        encoding="utf-8",
    )
    second = tmp_path / "second.py"
    second.write_text(
        """
# /// script
# dependencies = ["pandas"]
# ///
""",
        encoding="utf-8",
    )
    assert script_metadata_hash_from_filename(
        str(first)
    ) != script_metadata_hash_from_filename(str(second))


def test_with_pinned_dependencies_pins_known_names() -> None:
    from marimo._utils.inline_script_metadata import (
        with_pinned_dependencies,
    )

    src = """# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "polars",
#     "duckdb>=1.0",
# ]
# ///

import polars
"""
    out = with_pinned_dependencies(
        src,
        {"polars": "1.20.0", "duckdb": "1.1.3"},
        lock_kind="resolved",
    )
    assert "polars==1.20.0" in out
    assert "duckdb==1.1.3" in out
    assert 'lock_kind = "resolved"' in out


def test_with_pinned_dependencies_leaves_unpinned_alone() -> None:
    from marimo._utils.inline_script_metadata import (
        with_pinned_dependencies,
    )

    src = """# /// script
# dependencies = [
#     "polars",
#     "scikit-learn",
# ]
# ///
"""
    out = with_pinned_dependencies(
        src,
        {"polars": "1.20.0"},
        lock_kind="observed",
    )
    assert "polars==1.20.0" in out
    # scikit-learn wasn't in pins; left untouched.
    assert "scikit-learn" in out
    assert "scikit-learn==" not in out


def test_with_pinned_dependencies_preserves_url_deps() -> None:
    from marimo._utils.inline_script_metadata import (
        with_pinned_dependencies,
    )

    src = """# /// script
# dependencies = [
#     "polars",
#     "private @ https://example.com/private-1.0-py3-none-any.whl",
# ]
# ///
"""
    out = with_pinned_dependencies(
        src,
        {"polars": "1.20.0", "private": "9.9.9"},
        lock_kind="resolved",
    )
    assert "polars==1.20.0" in out
    assert "https://example.com/private-1.0-py3-none-any.whl" in out
    assert "private==9.9.9" not in out


def test_with_pinned_dependencies_canonicalizes_names() -> None:
    from marimo._utils.inline_script_metadata import (
        with_pinned_dependencies,
    )

    src = """# /// script
# dependencies = ["Scikit_Learn"]
# ///
"""
    out = with_pinned_dependencies(
        src,
        {"scikit-learn": "1.5.0"},
        lock_kind="observed",
    )
    assert "Scikit_Learn==1.5.0" in out


def test_with_pinned_dependencies_no_block_returns_unchanged() -> None:
    from marimo._utils.inline_script_metadata import (
        with_pinned_dependencies,
    )

    src = "import polars\n"
    out = with_pinned_dependencies(
        src,
        {"polars": "1.20.0"},
        lock_kind="resolved",
    )
    assert out == src


# ----- pin_pep723_dependencies_for_wasm -------------------------------------


class _FakeDist:
    """Minimal stand-in for `importlib.metadata.Distribution`."""

    def __init__(self, name: str, version: str) -> None:
        self.metadata = {"Name": name}
        self.version = version


_WASM_SRC = """# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "numpy",
#     "pandas",
#     "jax",
# ]
# ///
"""


def _wasm_path(tmp_path: Path) -> object:
    from marimo._utils.marimo_path import MarimoPath

    script = tmp_path / "notebook.py"
    script.write_text(_WASM_SRC)
    return MarimoPath(script)


def test_pin_for_wasm_pins_to_lockfile_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins to the lockfile version, not the locally installed one."""
    import importlib.metadata

    from marimo._utils.inline_script_metadata import (
        pin_pep723_dependencies_for_wasm,
    )

    monkeypatch.delenv("MARIMO_HTML_WASM_SANDBOX_BOOTSTRAPPED", raising=False)
    monkeypatch.setattr(
        importlib.metadata,
        "distributions",
        lambda: [_FakeDist("numpy", "1.99.0"), _FakeDist("pandas", "2.99.0")],
    )
    # Need to patch where it's looked up. The function imports inside its
    # body, so patch the source module.
    import marimo._pyodide.pyodide_constraints as constraints

    monkeypatch.setattr(
        constraints,
        "fetch_pyodide_package_versions",
        lambda: {"numpy": "2.0.2", "pandas": "2.2.3"},
    )

    out = pin_pep723_dependencies_for_wasm(_WASM_SRC, _wasm_path(tmp_path))
    assert "numpy==2.0.2" in out
    assert "pandas==2.2.3" in out
    # Locally-installed mismatched version should NOT appear.
    assert "numpy==1.99.0" not in out
    assert "pandas==2.99.0" not in out
    # jax isn't in the lockfile, left unpinned.
    assert "jax" in out
    assert "jax==" not in out
    assert 'lock_kind = "observed"' in out


def test_pin_for_wasm_lock_kind_resolved_inside_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bootstrap env var flips lock_kind to "resolved"."""
    import importlib.metadata

    from marimo._utils.inline_script_metadata import (
        pin_pep723_dependencies_for_wasm,
    )

    monkeypatch.setenv("MARIMO_HTML_WASM_SANDBOX_BOOTSTRAPPED", "1")
    monkeypatch.setattr(
        importlib.metadata,
        "distributions",
        lambda: [_FakeDist("numpy", "2.0.2")],
    )
    import marimo._pyodide.pyodide_constraints as constraints

    monkeypatch.setattr(
        constraints,
        "fetch_pyodide_package_versions",
        lambda: {"numpy": "2.0.2"},
    )

    out = pin_pep723_dependencies_for_wasm(_WASM_SRC, _wasm_path(tmp_path))
    assert 'lock_kind = "resolved"' in out


def test_pin_for_wasm_warns_about_non_pyodide_deps(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Top-level deps not in the pyodide lockfile trigger a stderr warning."""
    import importlib.metadata

    from marimo._utils.inline_script_metadata import (
        pin_pep723_dependencies_for_wasm,
    )

    monkeypatch.setattr(
        importlib.metadata,
        "distributions",
        lambda: [_FakeDist("numpy", "2.0.2")],
    )
    import marimo._pyodide.pyodide_constraints as constraints

    monkeypatch.setattr(
        constraints,
        "fetch_pyodide_package_versions",
        lambda: {"numpy": "2.0.2"},
    )

    pin_pep723_dependencies_for_wasm(_WASM_SRC, _wasm_path(tmp_path))
    err = capsys.readouterr().err
    # jax and pandas aren't in the lockfile mock; both should be flagged.
    assert "jax" in err
    assert "pandas" in err
    # numpy is in the lockfile; should not be flagged.
    assert "numpy" not in err


def test_pin_for_wasm_falls_back_to_installed_on_fetch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the lockfile is unreachable, we still pin from the local env."""
    import importlib.metadata

    from marimo._utils.inline_script_metadata import (
        pin_pep723_dependencies_for_wasm,
    )

    monkeypatch.setattr(
        importlib.metadata,
        "distributions",
        lambda: [_FakeDist("numpy", "1.99.0")],
    )
    import marimo._pyodide.pyodide_constraints as constraints

    def _boom() -> dict[str, str]:
        raise RuntimeError("offline")

    monkeypatch.setattr(constraints, "fetch_pyodide_package_versions", _boom)

    out = pin_pep723_dependencies_for_wasm(_WASM_SRC, _wasm_path(tmp_path))
    # Fall-through path pins to whatever's installed.
    assert "numpy==1.99.0" in out
