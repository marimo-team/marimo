# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.builder import _join_params, h


def test_div() -> None:
    assert h.div("Hello") == "<div>Hello</div>"
    assert h.div(["Hello", "World"]) == "<div>HelloWorld</div>"
    assert (
        h.div("Hello", style="color:red")
        == "<div style='color:red'>Hello</div>"
    )


def test_img() -> None:
    assert h.img() == "<img />"
    assert (
        h.img(src="image.jpg", alt="image", style="width:100px")
        == "<img src='image.jpg' alt='image' style='width:100px' />"
    )


def test_video() -> None:
    assert h.video() == "<video controls></video>"
    assert (
        h.video(src="video.mp4", controls=False)
        == "<video src='video.mp4'></video>"
    )


def test_audio() -> None:
    assert h.audio() == "<audio controls></audio>"
    assert (
        h.audio(src="audio.mp3", controls=False)
        == "<audio src='audio.mp3'></audio>"
    )


def test_iframe() -> None:
    assert h.iframe() == "<iframe frameborder='0'></iframe>"
    assert (
        h.iframe(src="https://marimo.io")
        == "<iframe src='https://marimo.io' frameborder='0'></iframe>"
    )


def test_pre() -> None:
    assert h.pre("Hello") == "<pre>Hello</pre>"
    assert h.pre("Hello", "color:red") == "<pre style='color:red'>Hello</pre>"


def test_join_params() -> None:
    assert (
        _join_params([("style", "color:red"), ("class", "my-class")])
        == "style='color:red' class='my-class'"
    )
    assert _join_params([]) == ""


def test_component() -> None:
    assert (
        h.component(
            "my-comp",
            [("style", "color:red"), ("class", "my-class")],
        )
        == "<my-comp style='color:red' class='my-class'></my-comp>"
    )

    assert h.component("my-comp", []) == "<my-comp></my-comp>"
