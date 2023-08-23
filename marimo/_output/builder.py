# Copyright 2023 Marimo. All rights reserved.
from typing import List, Optional, Tuple, Union


class _HTMLBuilder:
    @staticmethod
    def div(
        children: Union[str, List[str]], style: Optional[str] = None
    ) -> str:
        resolved_children = (
            [children] if isinstance(children, str) else children
        )

        params: List[Tuple[str, str]] = []
        if style:
            params.append(("style", style))

        children_html = "".join(resolved_children)

        if len(params) == 0:
            return f"<div>{children_html}</div>"
        else:
            return f"<div {_join_params(params)}>{children_html}</div>"

    @staticmethod
    def img(
        src: Optional[str] = None,
        alt: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        params: List[Tuple[str, str]] = []
        if src:
            params.append(("src", src))
        if alt:
            params.append(("alt", alt))
        if style:
            params.append(("style", style))

        if len(params) == 0:
            return "<img />"
        else:
            return f"<img {_join_params(params)} />"


def _join_params(params: List[Tuple[str, str]]) -> str:
    return " ".join([f"{k}='{v}'" for k, v in params])


h = _HTMLBuilder()
