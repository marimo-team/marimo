# Copyright 2023 Marimo. All rights reserved.
from marimo._output.builder import _join_params, h


def test_div() -> None:
    assert h.div("Hello") == "<div>Hello</div>"
    assert h.div(["Hello", "World"]) == "<div>HelloWorld</div>"
    assert h.div("Hello", "color:red") == "<div style='color:red'>Hello</div>"


def test_img() -> None:
    assert h.img() == "<img />"
    assert (
        h.img(src="image.jpg", alt="image", style="width:100px")
        == "<img src='image.jpg' alt='image' style='width:100px' />"
    )


def test_audio() -> None:
    assert h.audio() == "<audio controls />"
    assert (
        h.audio(src="audio.mp3", controls=False) == "<audio src='audio.mp3' />"
    )


def test_iframe() -> None:
    assert h.iframe() == "<iframe />"
    assert (
        h.iframe(src="https://marimo.io")
        == "<iframe src='https://marimo.io' />"
    )


def test_pre() -> None:
    assert h.pre("Hello") == "<pre>Hello</pre>"
    assert h.pre("Hello", "color:red") == "<pre style='color:red'>Hello</pre>"


def test_join_params() -> None:
    assert (
        _join_params([("style", "color:red"), ("class", "myClass")])
        == "style='color:red' class='myClass'"
    )
    assert _join_params([]) == ""
