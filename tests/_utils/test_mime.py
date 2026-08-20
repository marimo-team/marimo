# Copyright 2026 Marimo. All rights reserved.
from pathlib import Path

from marimo._utils.mime import guess_mime_type


def test_guess_mime_type() -> None:
    assert guess_mime_type("notes.txt") == "text/plain"
    assert guess_mime_type("file-without-extension") is None


def test_guess_custom_mime_type() -> None:
    assert guess_mime_type("pyproject.toml") == "application/toml"
    assert guess_mime_type("CONFIG.TOML") == "application/toml"
    assert (
        guess_mime_type("s3://bucket/pyproject.toml?version=1")
        == "application/toml"
    )
    assert guess_mime_type(Path("pyproject.toml")) == "application/toml"


def test_guess_mime_type_from_url_path() -> None:
    assert (
        guess_mime_type("https://example.com/report.pdf?signature=secret")
        == "application/pdf"
    )
    assert (
        guess_mime_type("s3://bucket/data.json?version=1#preview")
        == "application/json"
    )
    assert guess_mime_type("//cdn.example.com/app.js?v=1") in {
        "application/javascript",
        "text/javascript",
    }


def test_windows_drive_is_not_treated_as_url_scheme() -> None:
    assert guess_mime_type(r"C:\project\pyproject.toml") == "application/toml"
