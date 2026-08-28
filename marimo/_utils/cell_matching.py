# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Sequence


def similarity_score(s1: str, s2: str) -> float:
    """Fast similarity score based on common prefix and suffix.
    Returns lower score for more similar strings."""
    # Find common prefix length
    prefix_len = 0
    for c1, c2 in zip(s1, s2, strict=False):
        if c1 != c2:
            break
        prefix_len += 1

    # Find common suffix length if strings differ in middle
    if prefix_len < min(len(s1), len(s2)):
        s1_rev = s1[::-1]
        s2_rev = s2[::-1]
        for suffix_len, (c1, c2) in enumerate(
            zip(s1_rev, s2_rev, strict=False), start=1
        ):
            if c1 != c2:
                suffix_len -= 1
                break
    else:
        suffix_len = 0

    # Return inverse similarity - shorter common affix means higher score
    return len(s1) + len(s2) - 2.0 * (prefix_len + suffix_len)


def group_lookup(
    ids: Sequence[CellId_t], codes: Sequence[str]
) -> dict[str, list[tuple[int, CellId_t]]]:
    lookup: dict[str, list[tuple[int, CellId_t]]] = {}
    for idx, (cell_id, code) in enumerate(zip(ids, codes, strict=False)):
        lookup.setdefault(code, []).append((idx, cell_id))
    return lookup


def extract_order(
    codes: list[str], lookup: dict[str, list[tuple[int, CellId_t]]]
) -> list[list[int]]:
    offset = 0
    order: list[list[int]] = [[]] * len(codes)
    for i, code in enumerate(codes):
        dupes = len(lookup[code])
        order[i] = [offset + j for j in range(dupes)]
        offset += dupes
    return order


def get_unique(
    codes: Sequence[str], available: dict[str, list[tuple[int, CellId_t]]]
) -> list[str]:
    # Order matters, required opposed to using set()
    seen = set(codes) - set(available.keys())
    unique_codes = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)
    return unique_codes


def pop_local(available: list[tuple[int, CellId_t]], idx: int) -> CellId_t:
    """Find and pop the index that is closest to idx"""
    # NB. by min implementation a preference is given to the lower index when equidistant
    best_idx = min(
        range(len(available)), key=lambda i: abs(available[i][0] - idx)
    )
    return available.pop(best_idx)[1]


# Above this size the exact O(n^3) solver gets slow on dense, tie-heavy cost
# matrices -- in particular the zero-padded matrices produced when many more
# cells are added than removed (~0.5s at n=500 for a realistic matrix, several
# seconds for the padded worst case). Such large simultaneous edits are rare and
# a slightly sub-optimal match there is harmless, so fall back to a fast O(n^2)
# greedy assignment above the cutoff.
_MAX_OPTIMAL_ASSIGNMENT_SIZE = 100


def _greedy_assignment(scores: list[list[float]]) -> list[int]:
    """Fast approximate assignment; `result[column] = row`, same convention as
    `_hungarian_algorithm`."""
    n = len(scores)
    result = [-1] * n
    used_row = [False] * n
    # Assign the most decisive columns (smallest best cost) first.
    for j in sorted(
        range(n), key=lambda c: min(scores[r][c] for r in range(n))
    ):
        best_row, best_cost = -1, float("inf")
        for i in range(n):
            if not used_row[i] and scores[i][j] < best_cost:
                best_cost, best_row = scores[i][j], i
        if best_row != -1:
            used_row[best_row] = True
            result[j] = best_row
    return result


def _hungarian_algorithm(scores: list[list[float]]) -> list[int]:
    """Solve the assignment problem, returning a minimum-cost matching.

    Uses the O(n^3) shortest-augmenting-path method (Jonker-Volgenant /
    Kuhn-Munkres), which is guaranteed to find an optimal assignment without
    additional dependencies. Links:
    - https://en.wikipedia.org/wiki/Hungarian_algorithm

    Returns a list `result` where `result[column] = row` for the row matched to
    each column (or -1 if unmatched, which only happens for an empty input).
    """
    n = len(scores)
    if n == 0:
        return []

    inf = float("inf")
    # Potentials (u for rows, v for columns) and the current column -> row
    # matching. Index 0 is a sentinel used while growing the augmenting path,
    # so everything is 1-indexed.
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    match_col_to_row = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        match_col_to_row[0] = i
        j0 = 0
        min_val = [inf] * (n + 1)
        used = [False] * (n + 1)
        # Grow an alternating tree until we reach an unmatched column.
        while True:
            used[j0] = True
            i0 = match_col_to_row[j0]
            delta = inf
            j1 = -1
            for j in range(1, n + 1):
                if not used[j]:
                    cur = scores[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < min_val[j]:
                        min_val[j] = cur
                        way[j] = j0
                    if min_val[j] < delta:
                        delta = min_val[j]
                        j1 = j
            # Update potentials so the reduced costs stay non-negative.
            for j in range(n + 1):
                if used[j]:
                    u[match_col_to_row[j]] += delta
                    v[j] -= delta
                else:
                    min_val[j] -= delta
            j0 = j1
            if match_col_to_row[j0] == 0:
                break
        # Augment along the path recorded in `way`.
        while j0:
            j1 = way[j0]
            match_col_to_row[j0] = match_col_to_row[j1]
            j0 = j1

    # Convert to result format: result[column] = row (0-indexed).
    result = [-1] * n
    for j in range(1, n + 1):
        if match_col_to_row[j] != 0:
            result[j - 1] = match_col_to_row[j] - 1

    return result


def _match_cell_ids_by_similarity(
    prev_ids: Sequence[CellId_t],
    prev_codes: Sequence[str],
    next_ids: Sequence[CellId_t],
    next_codes: Sequence[str],
) -> list[CellId_t]:
    """Match cell IDs based on code similarity."""
    assert len(prev_codes) == len(prev_ids)
    assert len(next_codes) == len(next_ids)

    # ids that are not in prev_ids but in next_ids
    id_pool = set(next_ids) - set(prev_ids)

    def get_next_available_id(idx: int) -> CellId_t:
        cell_id = next_ids[idx]
        # Use the id from the pool if available
        if cell_id in id_pool:
            id_pool.remove(cell_id)
        elif id_pool:
            # Otherwise just use the next available id
            cell_id = id_pool.pop()
        else:
            # If no ids are available, we could generate a new one
            # but this should never run.
            raise RuntimeError(
                "No available IDs left to assign. This should not happen."
            )
        return cell_id

    def filter_and_backfill() -> list[CellId_t]:
        for idx, _ in enumerate(next_ids):
            if result[idx] is None:
                # If we have a None, we need to fill it with an available ID
                result[idx] = get_next_available_id(idx)
        # Only needed to appease the type checker. We just filled all None
        # values.
        return [_id for _id in result if _id is not None]

    # Hash matching to capture permutations
    # covers next is a subset of prev (i.e. next - prev == {})
    previous_lookup = group_lookup(prev_ids, prev_codes)
    next_lookup = group_lookup(next_ids, next_codes)

    result: list[CellId_t | None] = [None] * len(next_codes)
    filled = 0
    for idx, code in enumerate(next_codes):
        if code in previous_lookup:
            # If we have an exact match, use it
            filled += 1
            result[idx] = pop_local(previous_lookup[code], idx)
            if not previous_lookup[code]:
                del previous_lookup[code]
            # Clean up the next_lookup match too.
            if code in next_lookup:
                pop_local(next_lookup[code], idx)
                if not next_lookup[code]:
                    del next_lookup[code]

    # If we filled all positions, return the result
    # or if prev is a subset of next, then prev has been dequeued and emptied,
    # we can just backfill and return.
    if filled == len(next_codes) or not previous_lookup:
        return filter_and_backfill()

    # The remaining case is (next - prev) is not empty.
    # Establish specific order of remaining unique codes so we can match them
    added_code = get_unique(next_codes, next_lookup)
    deleted_code = get_unique(prev_codes, previous_lookup)

    # Build order mappings for the Hungarian algorithm
    next_order = extract_order(added_code, next_lookup)
    prev_order = extract_order(deleted_code, previous_lookup)

    # grab indices for lookup
    next_inverse = {code: i for i, code in enumerate(added_code)}
    # and inverse mapping for prev
    inverse_order = {
        idx: i for i, idxs in enumerate(prev_order) for idx in idxs
    }

    # Pad the scores matrix to ensure it is square
    n = max(len(next_codes) - filled, len(prev_codes) - filled)
    scores = [[0.0] * n for _ in range(n)]
    # Fill matrix, accounting for dupes
    for i, code in enumerate(added_code):
        for j, prev_code in enumerate(deleted_code):
            score = similarity_score(prev_code, code)
            for x in next_order[i]:
                for y in prev_order[j]:
                    # NB. transposed indices for Hungarian
                    scores[y][x] = score

    # Use the exact assignment for small problems, and a fast greedy fallback
    # for large ones where the exact O(n^3) solver would be too slow.
    matches = (
        _greedy_assignment(scores)
        if n > _MAX_OPTIMAL_ASSIGNMENT_SIZE
        else _hungarian_algorithm(scores)
    )
    for idx, code in enumerate(next_codes):
        if result[idx] is None:
            match_idx = next_order[next_inverse[code]].pop(0)
            if match_idx != -1 and matches[match_idx] in inverse_order:
                prev_idx = inverse_order[matches[match_idx]]
                prev_code = deleted_code[prev_idx]
                result[idx] = pop_local(previous_lookup[prev_code], idx)

    return filter_and_backfill()


def match_cell_ids_by_similarity(
    prev_data: dict[CellId_t, str], next_data: dict[CellId_t, str]
) -> dict[CellId_t, CellId_t]:
    """Match cell IDs based on code similarity.

    NB. There is similar code in the front end that matches session results to
    cells, but there are a few caveats for why the logic is different:
      - Session matching is inherent order dependent. If the order is wrong,
        there is no match. Moreover, the code must be an exact match for a
        session to be paired.
      - Cell matching in this context is not order dependent, we assume the
        notebook can be totally scrambled and we still want to match. Lose cell
        matching is also allowed.
    As such, in the frontend case a Lavenshtein edit is used to match cells to
    session results based on code.
    While here we can naively use a direct match, and non-matching cells are still
    attempted to match based on some similarity metric.

    Args:
        prev_data: Mapping of previous cell IDs to code
        next_data: Mapping of next cell IDs to code

    Returns:
        A map of old ids to new ids, using prev_ids where possible
    """

    prev_ids, prev_codes = zip(*prev_data.items(), strict=False)
    next_ids, next_codes = zip(*next_data.items(), strict=False)

    sorted_ids = _match_cell_ids_by_similarity(
        prev_ids,
        prev_codes,
        next_ids,
        next_codes,
    )

    return dict(zip(sorted_ids, next_ids, strict=False))
