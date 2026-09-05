# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import itertools
import random

from marimo._utils.cell_matching import (
    _greedy_assignment,
    _hungarian_algorithm,
    match_cell_ids_by_similarity,
)


def _assignment_cost(scores: list[list[float]], result: list[int]) -> float:
    """Total cost of the matching returned by _hungarian_algorithm.

    `result[column] = row`; raises if the matching is not a permutation.
    """
    n = len(scores)
    col_to_row = {j: result[j] for j in range(n) if result[j] != -1}
    assert len(col_to_row) == n, "matching is not complete"
    assert len(set(col_to_row.values())) == n, "matching is not a permutation"
    return sum(scores[row][col] for col, row in col_to_row.items())


def _brute_force_optimal(scores: list[list[float]]) -> float:
    n = len(scores)
    return min(
        sum(scores[i][perm[i]] for i in range(n))
        for perm in itertools.permutations(range(n))
    )


def test_hungarian_empty() -> None:
    assert _hungarian_algorithm([]) == []


def test_hungarian_single() -> None:
    assert _hungarian_algorithm([[5.0]]) == [0]


def test_hungarian_known_suboptimal_case() -> None:
    # Regression test: the previous covering heuristic returned a cost-17
    # assignment here; the optimal cost is 13.
    scores = [
        [7.0, 7.0, 8.0],
        [3.0, 5.0, 3.0],
        [3.0, 7.0, 4.0],
    ]
    result = _hungarian_algorithm(scores)
    assert _assignment_cost(scores, result) == 13.0
    assert _assignment_cost(scores, result) == _brute_force_optimal(scores)


def test_hungarian_matches_brute_force() -> None:
    # The assignment must be optimal for every matrix, not merely valid.
    rng = random.Random(20260825)
    for _ in range(500):
        n = rng.randint(1, 6)
        scores = [
            [float(rng.randint(0, 9)) for _ in range(n)] for _ in range(n)
        ]
        result = _hungarian_algorithm([row[:] for row in scores])
        assert _assignment_cost(scores, result) == _brute_force_optimal(scores)


def test_hungarian_handles_negative_and_float_costs() -> None:
    rng = random.Random(1234)
    for _ in range(200):
        n = rng.randint(1, 5)
        scores = [[rng.uniform(-5.0, 5.0) for _ in range(n)] for _ in range(n)]
        result = _hungarian_algorithm([row[:] for row in scores])
        assert (
            abs(
                _assignment_cost(scores, result) - _brute_force_optimal(scores)
            )
            < 1e-9
        )


def test_greedy_assignment_returns_valid_permutation() -> None:
    rng = random.Random(7)
    for _ in range(50):
        n = rng.randint(1, 25)
        scores = [[rng.uniform(-5.0, 5.0) for _ in range(n)] for _ in range(n)]
        result = _greedy_assignment([row[:] for row in scores])
        assert sorted(result) == list(range(n))


def test_greedy_assignment_scales_to_large_inputs() -> None:
    # The exact O(n^3) solver is too slow on large, tie-heavy padded matrices
    # (several seconds at n=500); the greedy fallback used above the size cutoff
    # must stay fast and still return a valid assignment.
    n = 500
    scores = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(20):
            scores[i][j] = float((i * 31 + j) % 97)
    result = _greedy_assignment(scores)
    assert sorted(result) == list(range(n))


def test_match_cell_ids_identical_notebook() -> None:
    data = {"a": "x = 1", "b": "y = 2", "c": "z = 3"}
    assert match_cell_ids_by_similarity(dict(data), dict(data)) == {
        "a": "a",
        "b": "b",
        "c": "c",
    }


def test_match_cell_ids_prefers_most_similar() -> None:
    # Every cell was edited (no exact matches), so matching falls back to the
    # similarity assignment. Each next cell should keep the id of the prev cell
    # it most closely resembles.
    prev = {
        "imp": "import pandas as pd",
        "tot": "x = compute_total(data)",
        "plt": "df.plot(kind='bar')",
    }
    nxt = {
        "n_plt": "df.plot(kind='line')",
        "n_tot": "x = compute_total(rows)",
        "n_imp": "import polars as pd",
    }
    mapping = match_cell_ids_by_similarity(dict(prev), dict(nxt))
    assert mapping == {"plt": "n_plt", "tot": "n_tot", "imp": "n_imp"}
