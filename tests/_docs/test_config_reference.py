# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Annotated

import markdown
from msgspec import UNSET, Meta, Struct, UnsetType, field, inspect as mi

from docs.config_reference import _render_fields, render_config_reference
from docs.hooks import on_page_markdown
from marimo._config.config_schema import MarimoConfig


def test_reference_includes_nested_and_container_options() -> None:
    output = render_config_reference()
    for path in (
        "display.theme",
        "ai.open_ai.api_key",
        "ai.custom_providers.<name>.api_key",
        "file_browser.folders[].path",
        "sharing.html",
        "mcp.mcpServers.<name>.command",
        "mcp.mcpServers.<name>.url",
        "cache.store.type",
        "cache.store[].type",
    ):
        assert f"`{path}`" in output
    assert "Literal['dark', 'light', 'system']" in output
    assert 'class="configuration-status configuration-deprecated"' in output
    assert '!!! warning "Deprecated"' not in output
    assert 'class="configuration-status configuration-experimental"' in output
    assert '!!! warning "Experimental"' not in output
    assert 'class="configuration-status configuration-sensitive"' in output
    assert "configuration-tooltip" not in output
    assert "<button" not in output
    assert '!!! note "Sensitive"' not in output


def test_reference_has_unique_linkable_headings() -> None:
    output = render_config_reference()
    anchors = re.findall(r"\{ #([^} ]+)[^}]*\}", output)
    assert len(anchors) == len(set(anchors))
    html = markdown.markdown(
        output, extensions=["attr_list", "admonition", "toc"]
    )
    assert 'id="file_browser-folders-item-path"' in html
    assert 'id="mcp-mcpservers-name-disabled-stdio"' in html
    assert 'id="mcp-mcpservers-name-disabled-http"' in html
    assert "&lt;name&gt;" in html


def test_categories_have_no_type_or_default() -> None:
    output = render_config_reference()
    assert "## Completion { #completion .configuration-category }" in output
    assert "## AI { #ai .configuration-category }" in output
    categories = re.split(r"^## ", output, flags=re.MULTILINE)[1:]
    assert len(categories) == len(MarimoConfig.__struct_fields__)
    for category in categories:
        introduction = category.split("\n### ", 1)[0]
        assert "**Type:**" not in introduction
        assert "**Default:**" not in introduction
    assert "### `display.theme`" in output


def test_defaults_do_not_evaluate_dynamic_factories() -> None:
    def dynamic_default() -> str:
        raise AssertionError(
            "Documentation must not evaluate dynamic defaults"
        )

    class Options(Struct, kw_only=True):
        dynamic: str = field(default_factory=dynamic_default)
        required: str
        unset: str | UnsetType = UNSET
        nullable: str | None = None
        empty: list[str] = field(default_factory=list)
        deprecated: Annotated[
            str,
            Meta(
                description="Use another setting.", extra={"deprecated": True}
            ),
        ] = "old"

    output = "\n".join(_render_fields(mi.type_info(Options), "options", 3))
    assert "**Default:** Dynamic (determined at runtime)." in output
    assert "**Default:** Required" in output
    unset_section = output.split("`options.unset`", 1)[1].split("### ", 1)[0]
    assert "**Type:** `str`" in unset_section
    assert "**Default:**" not in unset_section
    assert "**Default:** `None`" in output
    assert "**Default:** `[]`" in output
    assert "Use another setting." in output


def test_hook_only_generates_reference_on_configuration_page() -> None:
    marker = "<!-- configuration-reference -->"
    page = SimpleNamespace(
        file=SimpleNamespace(src_uri="api/configuration.md"), meta={}
    )
    output = on_page_markdown(marker, page)
    assert marker not in output
    assert "`display.theme`" in output
    page.file.src_uri = "api/index.md"
    assert on_page_markdown(marker, page) == marker
