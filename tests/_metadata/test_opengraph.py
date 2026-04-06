from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from marimo._metadata.opengraph import (
    DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR,
    OpenGraphConfig,
    default_opengraph_image,
    default_opengraph_image_abs,
    read_opengraph_from_file,
    read_opengraph_from_pyproject,
    resolve_opengraph_metadata,
)

if TYPE_CHECKING:
    import pytest


def test_read_opengraph_from_pyproject() -> None:
    pyproject = {
        "tool": {
            "marimo": {
                "opengraph": {
                    "title": "My Title",
                    "description": "My Description",
                    "image": "__marimo__/opengraph.png",
                }
            }
        }
    }

    assert read_opengraph_from_pyproject(pyproject) == OpenGraphConfig(
        title="My Title",
        description="My Description",
        image="__marimo__/opengraph.png",
        generator=None,
    )

    # Invalid shapes should be ignored.
    assert (
        read_opengraph_from_pyproject(
            {"tool": {"marimo": {"opengraph": {"title": 123}}}}
        )
        is None
    )


def test_read_opengraph_from_file(tmp_path) -> None:
    script = textwrap.dedent(
        """
        # /// script
        # [tool.marimo.opengraph]
        # title = "Hello World"
        # description = "A notebook"
        # image = "__marimo__/opengraph.png"
        # ///
        """
    ).lstrip()

    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    assert read_opengraph_from_file(str(path)) == OpenGraphConfig(
        title="Hello World",
        description="A notebook",
        image="__marimo__/opengraph.png",
        generator=None,
    )


def test_resolve_opengraph_metadata_defaults(tmp_path) -> None:
    script = "import marimo as mo\napp = mo.App()\n"
    path = tmp_path / "my_notebook.py"
    path.write_text(script, encoding="utf-8")

    resolved = resolve_opengraph_metadata(str(path))
    assert resolved.title == "My Notebook"
    assert resolved.description is None
    assert resolved.image is None


def test_resolve_opengraph_metadata_uses_app_title(tmp_path) -> None:
    script = textwrap.dedent(
        """
        # /// script
        # [tool.marimo.opengraph]
        # description = "desc"
        # ///
        import marimo as mo
        app = mo.App(app_title="App Title")
        """
    ).lstrip()
    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    resolved = resolve_opengraph_metadata(str(path), app_title="App Title")
    assert resolved.title == "App Title"
    assert resolved.description == "desc"


def test_resolve_opengraph_metadata_defaults_image_if_present(
    tmp_path,
) -> None:
    script = "import marimo as mo\napp = mo.App()\n"
    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    image_abs = default_opengraph_image_abs(str(path))
    image_abs.parent.mkdir(parents=True, exist_ok=True)
    image_abs.write_bytes(b"fake-png")

    resolved = resolve_opengraph_metadata(str(path))
    assert resolved.image == default_opengraph_image(str(path))


def test_resolve_opengraph_metadata_supports_https_url_image(tmp_path) -> None:
    script = textwrap.dedent(
        """
        # /// script
        # [tool.marimo.opengraph]
        # image = "https://example.com/opengraph.png"
        # ///
        import marimo as mo
        app = mo.App()
        """
    ).lstrip()
    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    resolved = resolve_opengraph_metadata(str(path))
    assert resolved.image == "https://example.com/opengraph.png"


def test_default_opengraph_image_abs_follows_pycache_prefix(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "prefix"
    monkeypatch.setattr("sys.pycache_prefix", str(prefix))

    notebook = tmp_path / "project" / "notebook.py"
    notebook.parent.mkdir(parents=True)
    notebook.touch()

    abs_path = default_opengraph_image_abs(str(notebook))
    # Should be under the prefix, not next to the notebook.
    assert str(abs_path).startswith(str(prefix))
    assert abs_path.name == "opengraph.png"
    assert "notebook" in abs_path.parts  # stem used as subdirectory


def test_default_image_exists_with_pycache_prefix(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_default_image_exists finds images under the relocated __marimo__ dir."""
    prefix = tmp_path / "prefix"
    monkeypatch.setattr("sys.pycache_prefix", str(prefix))

    notebook = tmp_path / "project" / "notebook.py"
    notebook.parent.mkdir(parents=True)
    notebook.touch()

    # Image at the relocated path.
    image = default_opengraph_image_abs(str(notebook))
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fake-png")

    from marimo._metadata.opengraph import _default_image_exists

    assert _default_image_exists(str(notebook))


def test_default_opengraph_placeholder_generator() -> None:
    image = DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR("Hello World")
    assert image.media_type == "image/svg+xml"
    assert image.content.startswith(b"<svg")
    assert b"Hello World" in image.content


def test_resolve_opengraph_metadata_merges_generator_overrides(
    tmp_path,
) -> None:
    script = textwrap.dedent(
        """
        # /// script
        # [tool.marimo.opengraph]
        # title = "Static Title"
        # generator = "generate_opengraph"
        # ///
        def generate_opengraph(ctx, parent):
            # Merge semantics: return only what you want to override.
            return {
                "image": "https://example.com/generated.png",
            }

        import marimo as mo
        app = mo.App()
        """
    ).lstrip()
    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    resolved = resolve_opengraph_metadata(str(path))
    assert resolved.title == "Static Title"
    assert resolved.image == "https://example.com/generated.png"


def test_resolve_opengraph_metadata_ignores_invalid_generator_signature(
    tmp_path,
) -> None:
    script = textwrap.dedent(
        """
        # /// script
        # [tool.marimo.opengraph]
        # title = "Static Title"
        # generator = "generate_opengraph"
        # ///
        def generate_opengraph(ctx, parent, extra):
            return {"image": "https://example.com/generated.png"}

        import marimo as mo
        app = mo.App()
        """
    ).lstrip()
    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    resolved = resolve_opengraph_metadata(str(path))
    assert resolved.title == "Static Title"
    assert resolved.image is None


def test_resolve_opengraph_metadata_supports_app_setup_imports(
    tmp_path,
) -> None:
    script = textwrap.dedent(
        """
        # /// script
        # [tool.marimo.opengraph]
        # title = "Static Title"
        # generator = "generate_opengraph"
        # ///
        import marimo
        app = marimo.App()

        with app.setup:
            import math

        @app.function
        def generate_opengraph(ctx, parent):
            return {"image": f"https://example.com/{math.floor(math.pi)}.png"}
        """
    ).lstrip()
    path = tmp_path / "notebook.py"
    path.write_text(script, encoding="utf-8")

    resolved = resolve_opengraph_metadata(str(path))
    assert resolved.title == "Static Title"
    assert resolved.image == "https://example.com/3.png"
