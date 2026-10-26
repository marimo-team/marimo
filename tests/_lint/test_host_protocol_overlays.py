# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote

import jsonpath
import pytest
from openapi_spec_validator import validate

from protocols.host.generate import ROOT, compose

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "selection",
    [
        None,
        "all",
        *(
            path.parent.name
            for path in sorted(ROOT.glob("experimental/*/overlay.yaml"))
        ),
    ],
)
def test_selected_contracts_are_valid(selection: str | None) -> None:
    document = compose(selection)
    validate(document)
    # OpenAPI validation does not resolve every schema reference, including
    # those in additionalProperties. Check each feature without its siblings.
    for ref in jsonpath.findall("$..['$ref']", document, strict=True):
        assert isinstance(ref, str)
        assert ref.startswith("#/")
        jsonpath.pointer.resolve(unquote(ref[1:]), document)


def test_analysis_selection_preserves_stable_contract() -> None:
    base = compose()
    combined = compose("all")
    assert combined == compose("analysis") == compose("analysis,analysis")
    assert combined["x-marimo-experimental"] == ["analysis"]
    assert combined["paths"] == base["paths"]
    schemas = combined["components"]["schemas"]
    original = base["components"]["schemas"]
    added = {"Analysis", "CellAnalysis", "AnalysisEvent", "AnalysisMessage"}
    assert schemas.keys() - original.keys() == added
    for name, schema in original.items():
        if name not in {"ObjectType", "Event"}:
            assert schemas[name] == schema
    assert schemas["ObjectType"]["enum"] == [
        *original["ObjectType"]["enum"],
        "analysis",
    ]
    assert schemas["Event"]["oneOf"] == [
        *original["Event"]["oneOf"],
        {"$ref": "#/components/schemas/AnalysisEvent"},
    ]
    assert schemas["Event"]["discriminator"]["mapping"] == {
        **original["Event"]["discriminator"]["mapping"],
        "analysis": "#/components/schemas/AnalysisEvent",
    }
    for name in added:
        assert schemas[name]["description"].startswith(
            "Experimental (analysis)."
        )
    assert compose() == base


@pytest.mark.parametrize(
    "selection", ["", "unknown", "analysis,unknown", "../analysis"]
)
def test_unknown_features_fail(selection: str) -> None:
    with pytest.raises(ValueError, match="Unknown experimental"):
        compose(selection)


def test_overlay_can_add_an_endpoint(tmp_path: Path) -> None:
    (tmp_path / "openapi.yaml").write_bytes(
        (ROOT / "openapi.yaml").read_bytes()
    )
    directory = tmp_path / "experimental" / "search"
    directory.mkdir(parents=True)
    (directory / "overlay.yaml").write_text(
        """\
overlay: 1.0.0
info:
  title: Search
  version: 0.1.0
actions:
  - target: $
    update:
      paths:
        /search:
          get:
            operationId: search
            responses:
              '200':
                description: Search results
                content:
                  application/json:
                    schema: { $ref: '#/components/schemas/SearchResults' }
      components:
        schemas:
          SearchResults:
            type: object
            properties:
              text: { type: string }
  - target: $.paths['/search'].get
    update:
      summary: Search notebooks
""",
        encoding="utf-8",
    )
    base = compose(root=tmp_path)
    document = compose("search", root=tmp_path)
    validate(document)
    assert {path: document["paths"][path] for path in base["paths"]} == base[
        "paths"
    ]
    assert document["paths"]["/search"]["get"]["summary"] == "Search notebooks"
    assert document["components"]["schemas"]["SearchResults"][
        "properties"
    ] == {"text": {"type": "string"}}
