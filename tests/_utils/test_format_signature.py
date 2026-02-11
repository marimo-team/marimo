# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.format_signature import format_signature


class TestFormatSignature:
    @pytest.mark.parametrize(
        ("sig", "expected_return"),
        [
            # Short (fits on 1 line)
            ("f() -> int", "int"),
            ("f() -> str", "str"),
            ("f() -> list[int]", "list[int]"),
            # Medium (multiline)
            ("f(x: int) -> Optional[str]", "Optional[str]"),
            ("f(x: int, y: str) -> dict[str, Any]", "dict[str, Any]"),
            ("medium_func(x: int, y: str) -> float", "float"),
            ("func(x: int, y: str = None) -> bool", "bool"),
            # Long (like hstack)
            (
                "hstack(items: Sequence[object], *, "
                'justify: str = "space-between", '
                "align: str = None, "
                "wrap: bool = False, "
                "gap: float = 0.5, "
                "widths: str = None) -> Html",
                "Html",
            ),
        ],
    )
    def test_return_type_preserved(
        self, sig: str, expected_return: str
    ) -> None:
        result = format_signature("def ", sig)
        assert "->" in result
        assert result.strip().endswith(expected_return)

    def test_no_return_type(self) -> None:
        result = format_signature("def ", "func(x: int, y: str)")
        assert "->" not in result
        assert "func" in result

    def test_class_prefix(self) -> None:
        result = format_signature("class ", "MyClass(x: int, y: str)")
        assert result.startswith("class ")
        assert "MyClass" in result

    def test_default_values_not_truncated(self) -> None:
        result = format_signature(
            "def ", "func(x: int, y: str = None) -> bool"
        )
        assert "None" in result
