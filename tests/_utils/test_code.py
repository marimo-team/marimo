# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.code import hash_code


def test_hash_code_deterministic() -> None:
    assert hash_code("print(1)") == hash_code("print(1)")


def test_hash_code_known_md5_hex() -> None:
    # md5("hello") with usedforsecurity=False
    assert hash_code("hello") == "5d41402abc4b2a76b9719d911017c592"
    assert len(hash_code("hello")) == 32


def test_hash_code_empty_string() -> None:
    digest = hash_code("")
    assert digest == "d41d8cd98f00b204e9800998ecf8427e"
    assert len(digest) == 32


def test_hash_code_distinct_inputs() -> None:
    assert hash_code("a") != hash_code("b")


def test_hash_code_unicode() -> None:
    assert hash_code("café") == hash_code("café")
    assert hash_code("café") != hash_code("cafe")
