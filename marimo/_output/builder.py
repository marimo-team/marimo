# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List, Optional, Tuple, Union


class _HTMLBuilder:
    @staticmethod
    def div(
        children: Union[str, List[str]], *, style: Optional[str] = None
    ) -> str:
        resolved_children = (
            [children] if isinstance(children, str) else children
        )

        params: List[Tuple[str, Union[str, None]]] = []
        if style:
            params.append(("style", style))

        children_html = "".join(resolved_children)

        if len(params) == 0:
            return f"<div>{children_html}</div>"
        else:
            return f"<div {_join_params(params)}>{children_html}</div>"

    @staticmethod
    def img(
        *,
        src: Optional[str] = None,
        alt: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        params: List[Tuple[str, Union[str, None]]] = []
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
    def video(
        *,
        src: Optional[str] = None,
        controls: bool = True,
        muted: bool = False,
        autoplay: bool = False,
        loop: bool = False,
        style: Optional[str] = None,
    ) -> str:
        params: List[Tuple[str, Union[str, None]]] = []
        if src:
            params.append(("src", src))
        if controls:
            params.append(("controls", ""))
        if style:
            params.append(("style", style))
        if muted:
            params.append(("muted", ""))
        if autoplay:
            params.append(("autoplay", ""))
        if loop:
            params.append(("loop", ""))

        if len(params) == 0:
            return "<video></video>"
        else:
            return f"<video {_join_params(params)}></video>"

    @staticmethod
    def audio(
        *,
        src: Optional[str] = None,
        controls: bool = True,
    ) -> str:
        params: List[Tuple[str, Union[str, None]]] = []
        if src:
            params.append(("src", src))
        if controls:
            params.append(("controls", ""))

        if len(params) == 0:
            return "<audio></audio>"
        else:
            return f"<audio {_join_params(params)}></audio>"

    @staticmethod
    def iframe(
        *,
        src: Optional[str] = None,
        srcdoc: Optional[str] = None,
        width: Optional[str] = None,
        height: Optional[str] = None,
        style: Optional[str] = None,
        onload: Optional[str] = None,
        # Opinionated defaults
        frameborder: Optional[str] = "0",
        **kwargs: str,
    ) -> str:
        params: List[Tuple[str, Union[str, None]]] = []
        if src:
            params.append(("src", src))
        if srcdoc:
            params.append(("srcdoc", srcdoc))
        if width:
            params.append(("width", width))
        if height:
            params.append(("height", height))
        if style:
            params.append(("style", style))
        if onload:
            params.append(("onload", onload))
        if frameborder:
            params.append(("frameborder", frameborder))
        for key, value in kwargs.items():
            params.append((key, value))

        if len(params) == 0:
            return "<iframe></iframe>"
        else:
            return f"<iframe {_join_params(params)}></iframe>"

    @staticmethod
    def pre(child: str, style: Optional[str] = None) -> str:
        params: List[Tuple[str, Union[str, None]]] = []
        if style is not None:
            params.append(("style", style))

        if not params:
            return f"<pre>{child}</pre>"
        else:
            return f"<pre {_join_params(params)}>{child}</pre>"

    @staticmethod
    def component(
        component_name: str,
        params: List[Tuple[str, Union[str, None]]],
    ) -> str:
        if len(params) == 0:
            return f"<{component_name}></{component_name}>"
        else:
            return (
                f"<{component_name} {_join_params(params)}></{component_name}>"
            )


def _join_params(params: List[Tuple[str, Union[str, None]]]) -> str:
    # Filter None
    params = [(k, v) for k, v in params if v is not None]

    return " ".join([f"{k}='{v}'" if v != "" else f"{k}" for k, v in params])


h = _HTMLBuilder()
