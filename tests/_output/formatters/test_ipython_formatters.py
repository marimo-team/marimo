from __future__ import annotations

import importlib
import importlib.abc
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.ipython_formatters import (
    IPythonFormatter,
    ReprMimeBundle,
)
from marimo._output.formatting import get_formatter

HAS_DEPS = DependencyManager.ipython.has()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_register_html_display():
    from IPython.display import HTML

    IPythonFormatter().register()

    # Test HTML with direct content
    html = HTML("<div>Hello World</div>")
    formatter = get_formatter(html)
    assert formatter is not None
    result = formatter(html)
    assert result == ("text/html", "<div>Hello World</div>")


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.append")
def test_display_patch(mock_append: MagicMock):
    from IPython.display import HTML, display

    unpatch = IPythonFormatter().register()
    try:
        # Test regular display
        obj = HTML("<div>Test</div>")
        display(obj)
        mock_append.assert_called_once_with(obj)
        mock_append.reset_mock()

        # Test raw mimebundle display
        mimebundle = {"text/html": "<div>Raw Test</div>"}
        display(mimebundle, raw=True)
        mock_append.assert_called_once()
        assert isinstance(mock_append.call_args[0][0], ReprMimeBundle)
        assert mock_append.call_args[0][0].data == mimebundle
    finally:
        unpatch()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_repr_mimebundle():
    data = {"text/html": "<div>Test</div>", "text/plain": "Test"}
    bundle = ReprMimeBundle(data)
    assert bundle._repr_mimebundle_() == data
    # Test that include/exclude params are ignored
    assert bundle._repr_mimebundle_(include=["text/html"]) == data


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_format_image_gif_bytes():
    from IPython.display import Image

    IPythonFormatter().register()

    # Minimal valid GIF
    gif_bytes = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
        b"\x01\x00\x00\x02\x02D\x01\x00;"
    )
    img = Image(data=gif_bytes, format="gif")
    formatter = get_formatter(img)
    assert formatter is not None
    mime_type, data = formatter(img)
    assert mime_type == "image/gif"
    assert data.startswith("data:image/gif;base64,")


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_format_image_png_bytes():
    from IPython.display import Image

    IPythonFormatter().register()

    # Minimal valid PNG (1x1 white pixel)
    import base64

    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
        "2mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg=="
    )
    png_bytes = base64.b64decode(png_b64)
    img = Image(data=png_bytes, format="png")
    formatter = get_formatter(img)
    assert formatter is not None
    mime_type, data = formatter(img)
    assert mime_type == "image/png"
    assert data.startswith("data:image/png;base64,")


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_format_image_url():
    from IPython.display import Image

    IPythonFormatter().register()

    img = Image(url="https://example.com/img.gif")
    formatter = get_formatter(img)
    assert formatter is not None
    mime_type, data = formatter(img)
    assert mime_type == "text/html"
    assert "https://example.com/img.gif" in data
    assert "<img" in data


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.append")
def test_display_html(mock_append: MagicMock):
    from IPython.display import display_html

    unpatch = IPythonFormatter().register()

    try:
        display_html("<div>Test</div>", raw=True)
        mock_append.assert_called_once()
        assert isinstance(mock_append.call_args[0][0], ReprMimeBundle)
        assert mock_append.call_args[0][0].data == {
            "text/html": "<div>Test</div>"
        }
    finally:
        unpatch()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.append")
def test_register_after_interrupted_first_import(
    mock_append: MagicMock,
):
    """Registering survives an interrupted first `import IPython`.

    An interrupted import drops `IPython` from `sys.modules` but keeps the
    submodules that finished loading, including `IPython.display`. Python
    binds `display` on the package only when the submodule is first loaded,
    so the re-imported package has no `display` attribute.
    """
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "IPython" or name.startswith("IPython.")
    }

    def drop_ipython(keep_display: bool = False) -> None:
        for name in [
            name
            for name in list(sys.modules)
            if (name == "IPython" or name.startswith("IPython."))
            and not (keep_display and name == "IPython.display")
        ]:
            del sys.modules[name]

    class InterruptMidInit(importlib.abc.MetaPathFinder):
        def find_spec(
            self,
            name: str,
            _path: Any = None,
            _target: Any = None,
        ) -> Any:
            # `IPython/__init__.py` imports this, so raising here aborts the
            # package import after it has started.
            if name == "IPython.core.interactiveshell":
                raise KeyboardInterrupt(name)
            return None

    try:
        # Load `IPython.display` once so that it survives the abort below.
        drop_ipython()
        importlib.import_module("IPython.display")
        drop_ipython(keep_display=True)

        sys.meta_path.insert(0, InterruptMidInit())
        try:
            with pytest.raises(KeyboardInterrupt):
                importlib.import_module("IPython")
        finally:
            sys.meta_path.remove(sys.meta_path[0])

        assert "IPython" not in sys.modules
        assert "IPython.display" in sys.modules

        ipython = importlib.import_module("IPython")
        assert not hasattr(ipython, "display")

        ipython_display = importlib.import_module("IPython.display")
        original_display = ipython_display.display

        unpatch = IPythonFormatter().register()
        try:
            html = ipython_display.HTML("<div>Test</div>")
            ipython_display.display(html)
            mock_append.assert_called_once_with(html)
            assert ipython_display.display is not original_display
        finally:
            unpatch()

        assert ipython_display.display is original_display
    finally:
        for name in [
            name
            for name in list(sys.modules)
            if name == "IPython" or name.startswith("IPython.")
        ]:
            del sys.modules[name]
        sys.modules.update(saved_modules)
