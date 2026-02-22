# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


def edit_distance(left: str, right: str) -> int:
    """Return the Levenshtein edit distance between two strings."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous_row = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current_row = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                current_row.append(previous_row[right_index - 1])
            else:
                current_row.append(
                    1
                    + min(
                        previous_row[right_index],
                        current_row[right_index - 1],
                        previous_row[right_index - 1],
                    )
                )
        previous_row = current_row
    return previous_row[-1]
