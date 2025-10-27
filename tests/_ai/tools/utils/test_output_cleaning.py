# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ai._tools.utils.output_cleaning import (
    clean_output,
    deduplicate_lines,
    normalize_progress_bars,
    strip_ansi_codes,
    truncate_output,
)


class TestStripAnsiCodes:
    def test_removes_color_codes(self) -> None:
        lines = ["\x1b[31mError\x1b[0m", "\x1b[32mSuccess\x1b[0m"]
        result = strip_ansi_codes(lines)
        assert result == ["Error", "Success"]

    def test_removes_bold_codes(self) -> None:
        lines = ["\x1b[1mBold text\x1b[0m"]
        result = strip_ansi_codes(lines)
        assert result == ["Bold text"]

    def test_removes_cursor_movement(self) -> None:
        lines = ["\x1b[2JCleared\x1b[H"]
        result = strip_ansi_codes(lines)
        assert result == ["Cleared"]

    def test_handles_no_ansi_codes(self) -> None:
        lines = ["Plain text", "No codes here"]
        result = strip_ansi_codes(lines)
        assert result == ["Plain text", "No codes here"]

    def test_empty_list(self) -> None:
        assert strip_ansi_codes([]) == []


class TestDeduplicateLines:
    def test_single_line(self) -> None:
        assert deduplicate_lines(["Hello"]) == ["Hello"]

    def test_two_identical_lines(self) -> None:
        result = deduplicate_lines(["Warning", "Warning"])
        assert result == ["Warning", "(repeated 2 times)"]

    def test_two_different_lines(self) -> None:
        result = deduplicate_lines(["Line 1", "Line 2"])
        assert result == ["Line 1", "Line 2"]

    def test_multiple_groups(self) -> None:
        lines = ["A", "A", "B", "B", "B", "C"]
        result = deduplicate_lines(lines)
        assert result == [
            "A",
            "(repeated 2 times)",
            "B",
            "(repeated 3 times)",
            "C",
        ]

    def test_all_identical(self) -> None:
        result = deduplicate_lines(["Same"] * 10)
        assert result == ["Same", "(repeated 10 times)"]

    def test_no_duplicates(self) -> None:
        lines = ["A", "B", "C", "D"]
        result = deduplicate_lines(lines)
        assert result == ["A", "B", "C", "D"]

    def test_empty_strings(self) -> None:
        lines = ["", "", "Text", "", ""]
        result = deduplicate_lines(lines)
        assert result == [
            "",
            "(repeated 2 times)",
            "Text",
            "",
            "(repeated 2 times)",
        ]

    def test_empty_list(self) -> None:
        assert deduplicate_lines([]) == []


class TestNormalizeProgressBars:
    def test_simple_carriage_return(self) -> None:
        lines = ["0%\r50%\r100%"]
        result = normalize_progress_bars(lines)
        assert result == ["100%"]

    def test_mixed_lines(self) -> None:
        lines = ["Start", "0%\r50%\r100%", "End"]
        result = normalize_progress_bars(lines)
        assert result == ["Start", "100%", "End"]

    def test_removes_empty_lines(self) -> None:
        lines = ["Text", "", "   ", "More"]
        result = normalize_progress_bars(lines)
        assert result == ["Text", "More"]

    def test_tqdm_style(self) -> None:
        lines = [
            "  0%|          | 0/100\r 50%|█████     | 50/100\r100%|██████████| 100/100"
        ]
        result = normalize_progress_bars(lines)
        assert result == ["100%|██████████| 100/100"]

    def test_no_carriage_returns(self) -> None:
        lines = ["Line 1", "Line 2"]
        result = normalize_progress_bars(lines)
        assert result == ["Line 1", "Line 2"]

    def test_empty_list(self) -> None:
        assert normalize_progress_bars([]) == []


class TestTruncateOutput:
    def test_no_truncation_when_under_limit(self) -> None:
        lines = [f"Line {i}" for i in range(5)]
        result = truncate_output(lines, max_lines=10)
        assert result == lines

    def test_truncates_middle(self) -> None:
        lines = [f"Line {i}" for i in range(1, 11)]
        result = truncate_output(lines, max_lines=5)
        assert len(result) == 6
        assert result[0] == "Line 1"
        assert result[1] == "Line 2"
        assert "truncated" in result[2]
        assert result[-2] == "Line 9"
        assert result[-1] == "Line 10"

    def test_keeps_head_and_tail(self) -> None:
        lines = [f"Epoch {i}" for i in range(1, 21)]
        result = truncate_output(lines, max_lines=6)
        assert result[0] == "Epoch 1"
        assert result[1] == "Epoch 2"
        assert result[2] == "Epoch 3"
        assert "truncated 14 lines" in result[3]
        assert result[-3] == "Epoch 18"
        assert result[-2] == "Epoch 19"
        assert result[-1] == "Epoch 20"

    def test_shows_correct_count(self) -> None:
        lines = ["x"] * 100
        result = truncate_output(lines, max_lines=10)
        assert any("truncated 90 lines" in line for line in result)

    def test_empty_list(self) -> None:
        assert truncate_output([]) == []


class TestCleanOutput:
    def test_full_pipeline_with_ansi_and_duplicates(self) -> None:
        lines = [
            "\x1b[32mStart\x1b[0m",
            "\x1b[33mWarning\x1b[0m",
            "\x1b[33mWarning\x1b[0m",
            "\x1b[33mWarning\x1b[0m",
        ]
        result = clean_output(lines)
        assert result == ["Start", "Warning", "(repeated 3 times)"]

    def test_full_pipeline_with_progress_bars(self) -> None:
        lines = [
            "Training",
            "0%\r50%\r100%",
            "Complete",
        ]
        result = clean_output(lines)
        assert result == ["Training", "100%", "Complete"]

    def test_combined_ml_workflow(self) -> None:
        lines = [
            "\x1b[1mEpoch 1/10\x1b[0m",
            "0%|          | 0/100\r100%|██████████| 100/100",
            "\x1b[34mLoss: 0.543\x1b[0m",
            "\x1b[1mEpoch 2/10\x1b[0m",
            "0%|          | 0/100\r100%|██████████| 100/100",
            "\x1b[34mLoss: 0.432\x1b[0m",
        ]
        result = clean_output(lines)
        assert result == [
            "Epoch 1/10",
            "100%|██████████| 100/100",
            "Loss: 0.543",
            "Epoch 2/10",
            "100%|██████████| 100/100",
            "Loss: 0.432",
        ]

    def test_empty_list(self) -> None:
        assert clean_output([]) == []
