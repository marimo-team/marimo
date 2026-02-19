# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from difflib import get_close_matches
from typing import TYPE_CHECKING

from marimo._utils.edit_distance import edit_distance

if TYPE_CHECKING:
    from collections.abc import Iterable


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _lower_map(candidates: Iterable[str]) -> dict[str, str]:
    lowered: dict[str, str] = {}
    for candidate in candidates:
        lowered.setdefault(candidate.lower(), candidate)
    return lowered


def suggest_commands(token: str, candidates: Iterable[str]) -> list[str]:
    """Suggest close command names using difflib then Levenshtein fallback."""
    lowered = _lower_map(candidates)
    if not lowered:
        return []

    token_lower = token.lower()
    if token_lower in lowered:
        return [lowered[token_lower]]

    close = get_close_matches(
        token_lower,
        list(lowered.keys()),
        n=3,
        cutoff=0.6,
    )
    if close:
        return [lowered[item] for item in close]

    ranked = sorted(
        (
            (edit_distance(token_lower, key), value)
            for key, value in lowered.items()
        ),
        key=lambda item: (item[0], item[1]),
    )
    if not ranked:
        return []

    min_distance = ranked[0][0]
    if min_distance > 2:
        return []

    closest_values = [
        value for distance, value in ranked if distance == min_distance
    ]
    return closest_values[:3]


def suggest_short_options(token: str, candidates: Iterable[str]) -> list[str]:
    """Suggest a single short-flag correction when the typo is unambiguous."""
    if not token.startswith("-") or token.startswith("--"):
        return []

    short_candidates = _dedupe(
        option
        for option in candidates
        if option.startswith("-") and not option.startswith("--")
    )
    if not short_candidates:
        return []

    token_lower = token.lower()
    exact = [opt for opt in short_candidates if opt.lower() == token_lower]
    if exact:
        return [exact[0]]

    ranked = sorted(
        (edit_distance(token, candidate), candidate)
        for candidate in short_candidates
    )
    best_distance = ranked[0][0]
    if best_distance > 1:
        return []

    best = [
        candidate
        for distance, candidate in ranked
        if distance == best_distance
    ]
    if len(best) != 1:
        return []

    return best
