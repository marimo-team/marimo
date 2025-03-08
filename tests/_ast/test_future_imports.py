# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.compiler import compile_cell, preprocess_future_imports
from marimo._types.ids import CellId_t


class TestFutureImports:
    @staticmethod
    def test_preprocess_future_imports() -> None:
        # Test with future import already at top
        code1 = """from __future__ import annotations
print('hello')"""
        # Future imports already at top should remain unchanged
        assert preprocess_future_imports(code1) == code1

        # Test with future import not at top
        code2 = """print('hello')
from __future__ import annotations"""
        expected2 = """from __future__ import annotations

print('hello')"""
        assert preprocess_future_imports(code2) == expected2

        # Test with multiple future imports
        code3 = """print('hello')
from __future__ import annotations
x = 1
from __future__ import division"""
        # Get the actual result to compare with
        result3 = preprocess_future_imports(code3)
        # Verify that future imports are at the top
        assert result3.startswith("from __future__ import annotations")
        assert "from __future__ import division" in result3.split("\n")[1]
        # Verify that the original code content is preserved
        assert "print('hello')" in result3
        assert "x = 1" in result3

        # Test with no future imports
        code4 = """print('hello')
x = 1"""
        assert preprocess_future_imports(code4) == code4

    @staticmethod
    def test_compile_with_future_import_not_at_top() -> None:
        # This test verifies that a cell with a future import not at the top
        # compiles successfully after the fix
        code = """print('hello')
from __future__ import annotations"""

        # This should not raise a SyntaxError
        cell = compile_cell(code, cell_id=CellId_t("test"))
        assert cell is not None
