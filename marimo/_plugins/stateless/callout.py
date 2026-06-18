# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

from marimo._output.formatting import as_html
from marimo._output.hypertext import ContainerHtml
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin

CalloutKind = Literal["neutral", "warn", "success", "info", "danger"]


@mddoc
class callout(ContainerHtml):
    """Build a callout output.

    Args:
        value: A value to render in the callout
        kind: The kind of callout (affects styling).

    Returns:
        Html (marimo.Html): An HTML object.
    """

    def __init__(
        self,
        value: object,
        kind: CalloutKind = "neutral",
    ) -> None:
        self._kind = kind
        super().__init__([as_html(value)])

    def _build_text(self) -> str:
        return build_stateless_plugin(
            component_name="marimo-callout-output",
            args={"html": self._children[0].text, "kind": self._kind},
        )
