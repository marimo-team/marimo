from __future__ import annotations

from marimo._cli.parse_args import parse_args


def test_parse_args_no_args():
    assert parse_args(()) == {}  # type: ignore
    assert parse_args("") == {}


def test_parse_args_non_dashed():
    assert parse_args(("foo", "bar")) == {}


def test_parse_args_with_integer():
    args = ("--count=10",)
    expected = {"count": 10}
    assert parse_args(args) == expected


def test_parse_args_with_float():
    args = ("--ratio=0.8",)
    expected = {"ratio": 0.8}
    assert parse_args(args) == expected


def test_parse_args_with_boolean():
    args: tuple[str] = ("--verbose=True", "--debug=false")
    expected = {"verbose": True, "debug": False}
    assert parse_args(args) == expected


def test_parse_args_with_string():
    args = ("--name=marimo",)
    expected = {"name": "marimo"}
    assert parse_args(args) == expected


def test_parse_args_with_short_option():
    args = ("-n", "--name", "-d", "--debug")
    expected = {
        "n": "",
        "name": "",
        "d": "",
        "debug": "",
    }
    assert parse_args(args) == expected


def test_parse_args_with_multiple_options():
    args = ("--name=marimo", "--count=10", "--verbose=True")
    expected = {"name": "marimo", "count": 10, "verbose": True}
    assert parse_args(args) == expected


def test_parse_args_with_spaces_or_equals():
    args = ("--name=marimo is cool", "--count", "10", "--key=abc=")
    expected = {"name": "marimo is cool", "count": 10, "key": "abc="}
    assert parse_args(args) == expected


def test_lists():
    args = (
        "--name=one",
        "--count",
        "10",
        "10",
        "--verbose=True",
        "--name=two",
        "--name=three",
    )
    expected = {
        "name": ["one", "two", "three"],
        "count": "10 10",
        "verbose": True,
    }
    assert parse_args(args) == expected
