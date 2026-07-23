# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

from marimo._output.formatting import as_html
from marimo._output.hypertext import ContainerHtml
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import (
    JSONType,
    build_stateless_plugin,
)

CalloutKind = Literal["neutral", "warn", "success", "info", "danger"]


@mddoc
class callout(ContainerHtml):
    """An `Html` callout object.

    Args:
        value: A value to render in the callout
        kind: The kind of callout (affects styling).
        title: An optional title.
    """

    def __init__(
        self,
        value: object,
        kind: CalloutKind = "neutral",
        title: str | None = None,
    ) -> None:
        self._kind = kind
        self._title = title
        super().__init__([as_html(value)])

    def _build_text(self) -> str:
        args: dict[str, JSONType] = {
            "html": self._children[0].text,
            "kind": self._kind,
        }
        if self._title is not None:
            args["title"] = self._title
        return build_stateless_plugin(
            component_name="marimo-callout-output",
            args=args,
        )
