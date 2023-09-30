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

    @staticmethod
    def audio(
        src: Optional[str] = None,
        controls: bool = True,
    ) -> str:
        params: List[Tuple[str, str]] = []
        if src:
            params.append(("src", src))
        if controls:
            params.append(("controls", ""))

        if len(params) == 0:
            return "<audio />"
        else:
            return f"<audio {_join_params(params)} />"

    @staticmethod
    def iframe(
        src: Optional[str] = None,
        width: Optional[str] = None,
        height: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        params: List[Tuple[str, str]] = []
        if src:
            params.append(("src", src))
        if width:
            params.append(("width", width))
        if height:
            params.append(("height", height))
        if style:
            params.append(("style", style))

        if len(params) == 0:
            return "<iframe />"
        else:
            return f"<iframe {_join_params(params)} />"

    @staticmethod
    def pre(child: str, style: Optional[str] = None) -> str:
        params: List[Tuple[str, str]] = []
        if style is not None:
            params.append(("style", style))

        if not params:
            return f"<pre>{child}</pre>"
        else:
            return f"<pre {_join_params(params)}>{child}</pre>"


def _join_params(params: List[Tuple[str, str]]) -> str:
    return " ".join([f"{k}='{v}'" if v != "" else f"{k}" for k, v in params])


h = _HTMLBuilder()
