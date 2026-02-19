# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.suggestions import (
    levenshtein_distance,
    suggest_commands,
    suggest_short_options,
)


def test_levenshtein_distance() -> None:
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("export", "export") == 0


def test_suggest_commands_close_match() -> None:
    candidates = ["edit", "export", "run", "tutorial"]
    assert suggest_commands("xport", candidates) == ["export"]


def test_suggest_commands_case_insensitive_exact() -> None:
    candidates = ["edit", "export", "run"]
    assert suggest_commands("EXPORT", candidates) == ["export"]


def test_suggest_short_option_case_variant() -> None:
    candidates = ["-p", "-h", "-q"]
    assert suggest_short_options("-P", candidates) == ["-p"]


def test_suggest_short_option_ambiguous_returns_empty() -> None:
    candidates = ["-p", "-q", "-d", "-h"]
    assert suggest_short_options("-Z", candidates) == []
