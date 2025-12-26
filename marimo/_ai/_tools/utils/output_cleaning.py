# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import re


def clean_output(lines: list[str]) -> list[str]:
    """Clean console output for LLM consumption."""
    lines = normalize_progress_bars(lines)
    lines = deduplicate_lines(lines)
    lines = strip_ansi_codes(lines)
    lines = truncate_output(lines)
    return lines


def strip_ansi_codes(lines: list[str]) -> list[str]:
    """Remove ANSI escape sequences (colors, formatting) from text.

    ANSI codes are used for terminal styling (colors, bold, cursor movement,
    etc.) from libraries like rich, pytest, click, tqdm, colorama. These are
    meaningless to LLMs and add noise to the output.
    """
    # Based on a widely cited Stack Overflow answer:
    # https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
    # Covers all 7-bit ANSI C1 escape sequences.
    ansi_pattern = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return [ansi_pattern.sub("", line) for line in lines]


def deduplicate_lines(lines: list[str]) -> list[str]:
    """Remove consecutive duplicate lines, replacing with a summary message.

    Useful for cleaning repetitive training logs, warnings, and batch processing output.
    """
    if len(lines) <= 1:
        return lines

    deduped_lines: list[str] = []
    prev_line = lines[0]
    repeat_count = 1

    for line in lines[1:]:
        if line == prev_line:
            repeat_count += 1
            continue
        # Flush previous group
        deduped_lines.append(prev_line)
        if repeat_count > 1:
            deduped_lines.append(f"(repeated {repeat_count} times)")

        # Start new group
        prev_line = line
        repeat_count = 1

    # Handle last group
    deduped_lines.append(prev_line)
    if repeat_count > 1:
        deduped_lines.append(f"(repeated {repeat_count} times)")

    return deduped_lines


def normalize_progress_bars(lines: list[str]) -> list[str]:
    """Collapse carriage return sequences to show only final state.

    Progress bars from tqdm, pandas.progress_apply(), dask, and Spark use
    carriage returns to overwrite the same line repeatedly. This keeps only
    the final state and removes empty lines.
    """
    normalized_lines: list[str] = []
    for line in lines:
        if "\r" in line:
            line = line.split("\r")[-1]
        if line.strip():
            normalized_lines.append(line)
    return normalized_lines


def truncate_output(lines: list[str], max_lines: int = 500) -> list[str]:
    """Keep first and last portions of output, truncating the middle."""
    if len(lines) <= max_lines:
        return lines

    keep_head = max_lines // 2
    keep_tail = max_lines - keep_head
    removed = len(lines) - max_lines

    return (
        lines[:keep_head]
        + [f"... [truncated {removed} lines] ..."]
        + lines[-keep_tail:]
    )
