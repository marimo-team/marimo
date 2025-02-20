from __future__ import annotations

import textwrap

import pytest

from marimo._utils.scripts import read_pyproject_from_script


def test_read_pyproject_from_script():
    script = textwrap.dedent(
        """
    # /// script
    # requires-python = ">=3.11"
    # dependencies = ["polars"]
    # [tool.marimo]
    # formatting = {line_length = 79}
    # ///

    import marimo
    """
    )

    pyproject = read_pyproject_from_script(script)
    assert pyproject is not None
    assert pyproject["requires-python"] == ">=3.11"
    assert pyproject["dependencies"] == ["polars"]
    assert pyproject["tool"]["marimo"]["formatting"]["line_length"] == 79

    # Test no script block
    script = "import marimo"
    assert read_pyproject_from_script(script) is None

    # Test multiple script blocks
    script = textwrap.dedent(
        """
    # /// script
    # requires-python = ">=3.11"
    # ///

    # /// script
    # dependencies = ["polars"]
    # ///
    """
    )
    with pytest.raises(ValueError, match="Multiple script blocks found"):
        read_pyproject_from_script(script)

    # Test invalid TOML
    script = textwrap.dedent(
        """
    # /// script
    # invalid toml content
    # ///
    """
    )
    with pytest.raises(ValueError):
        read_pyproject_from_script(script)


def test_read_marimo_config_from_script():
    script = textwrap.dedent(
        """
    # /// script
    # [tool.marimo.runtime]
    # watcher_on_save = "autorun"
    # auto_instantiate = true
    # output_max_bytes = 20
    # std_stream_max_bytes = 10
    # [tool.marimo.display]
    # cell_output = "above"
    # ///
    """
    )
    config = read_pyproject_from_script(script)
    assert config is not None
    assert config["tool"]["marimo"]["runtime"]["auto_instantiate"] is True
    assert config["tool"]["marimo"]["runtime"]["watcher_on_save"] == "autorun"
    assert config["tool"]["marimo"]["runtime"]["output_max_bytes"] == 20
    assert config["tool"]["marimo"]["runtime"]["std_stream_max_bytes"] == 10
    assert config["tool"]["marimo"]["display"]["cell_output"] == "above"
