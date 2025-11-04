# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._messaging.errors import (
    CycleError,
    ImportStarError,
    MarimoAncestorPreventedError,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInternalError,
    MarimoInterruptionError,
    MarimoStrictExecutionError,
    MarimoSyntaxError,
    MultipleDefinitionError,
    UnknownError,
    is_sensitive_error,
    is_unexpected_error,
)


class TestErrorClasses:
    def test_cycle_error(self) -> None:
        # Create a cycle error with mock edges
        # EdgeWithVar is a tuple of (start_cell_id, variables, end_cell_id)
        edge1 = ("cell1", ["var1"], "cell2")
        edge2 = ("cell2", ["var2"], "cell1")

        error = CycleError(edges_with_vars=(edge1, edge2))

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "cycle"
        assert "cycle" in error.describe().lower()
        assert isinstance(error.describe(), str)

    def test_multiple_definition_error(self) -> None:
        error = MultipleDefinitionError(
            name="test_var", cells=("cell1", "cell2")
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "multiple-defs"
        assert "test_var" in error.describe()
        assert "defined by another cell" in error.describe()

    def test_import_star_error(self) -> None:
        error = ImportStarError(msg="Cannot use import * in this context")

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "import-star"
        assert error.describe() == "Cannot use import * in this context"

    def test_import_star_error_with_lineno(self) -> None:
        error = ImportStarError(
            msg="Cannot use import * in this context", lineno=3
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "import-star"
        assert error.describe() == "Cannot use import * in this context"
        assert error.lineno == 3

    def test_marimo_interruption_error(self) -> None:
        error = MarimoInterruptionError()

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "interruption"
        assert "interrupted" in error.describe().lower()
        assert "re-run" in error.describe().lower()

    def test_marimo_ancestor_prevented_error(self) -> None:
        error = MarimoAncestorPreventedError(
            msg="Execution prevented by ancestor",
            raising_cell="cell1",
            blamed_cell="cell2",
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "ancestor-prevented"
        assert error.describe() == "Execution prevented by ancestor"
        assert error.raising_cell == "cell1"
        assert error.blamed_cell == "cell2"

    def test_marimo_ancestor_stopped_error(self) -> None:
        error = MarimoAncestorStoppedError(
            msg="Execution stopped by ancestor",
            raising_cell="cell1",
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "ancestor-stopped"
        assert error.describe() == "Execution stopped by ancestor"
        assert error.raising_cell == "cell1"

    def test_marimo_exception_raised_error(self) -> None:
        error = MarimoExceptionRaisedError(
            msg="ValueError: invalid value",
            exception_type="ValueError",
            raising_cell="cell1",
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "exception"
        assert error.describe() == "ValueError: invalid value"
        assert error.raising_cell == "cell1"
        assert error.exception_type == "ValueError"

    def test_marimo_syntax_error(self) -> None:
        error = MarimoSyntaxError(msg="Invalid syntax", lineno=5)

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "syntax"
        assert error.describe() == "Invalid syntax"
        assert error.lineno == 5

    def test_marimo_syntax_error_without_lineno(self) -> None:
        error = MarimoSyntaxError(msg="Invalid syntax")

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "syntax"
        assert error.describe() == "Invalid syntax"
        assert error.lineno is None

    def test_marimo_syntax_error_with_line_zero(self) -> None:
        # Edge case: line 0 should be treated as valid
        error = MarimoSyntaxError(msg="Invalid syntax", lineno=0)

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "syntax"
        assert error.describe() == "Invalid syntax"
        assert error.lineno == 0

    def test_marimo_syntax_error_with_large_lineno(self) -> None:
        # Test with larger line numbers
        error = MarimoSyntaxError(msg="Invalid syntax", lineno=100)

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "syntax"
        assert error.describe() == "Invalid syntax"
        assert error.lineno == 100

    def test_unknown_error(self) -> None:
        error = UnknownError(msg="Something went wrong")

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "unknown"
        assert error.describe() == "Something went wrong"

    def test_marimo_strict_execution_error(self) -> None:
        error = MarimoStrictExecutionError(
            msg="Strict execution error",
            ref="some_reference",
            blamed_cell="cell1",
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "strict-exception"
        assert error.describe() == "Strict execution error"
        assert error.ref == "some_reference"
        assert error.blamed_cell == "cell1"

    def test_marimo_internal_error(self) -> None:
        error = MarimoInternalError(
            error_id="test-error-id",
            msg="Original error message",
        )

        # Test properties
        serialized = msgspec.to_builtins(error)
        assert serialized["type"] == "internal"
        assert "An internal error occurred" in error.describe()
        assert "test-error-id" in error.describe()
        # The original message should be replaced with a generic one
        assert error.describe() != "Original error message"


class TestErrorUtilityFunctions:
    def test_is_unexpected_error(self) -> None:
        # These errors are expected/intentional
        assert not is_unexpected_error(
            MarimoAncestorPreventedError(
                msg="", raising_cell="cell1", blamed_cell=None
            )
        )
        assert not is_unexpected_error(
            MarimoAncestorStoppedError(msg="", raising_cell="cell1")
        )
        assert not is_unexpected_error(MarimoInterruptionError())

        # These errors are unexpected
        assert is_unexpected_error(
            MarimoExceptionRaisedError(
                msg="", exception_type="", raising_cell=None
            )
        )
        assert is_unexpected_error(MarimoSyntaxError(msg=""))
        assert is_unexpected_error(UnknownError(msg=""))

    def test_is_sensitive_error(self) -> None:
        # These errors are not sensitive
        assert not is_sensitive_error(
            MarimoAncestorPreventedError(
                msg="", raising_cell="cell1", blamed_cell=None
            )
        )
        assert not is_sensitive_error(
            MarimoAncestorStoppedError(msg="", raising_cell="cell1")
        )
        assert not is_sensitive_error(MarimoInternalError(error_id=""))

        # These errors are sensitive
        assert is_sensitive_error(
            MarimoExceptionRaisedError(
                msg="", exception_type="", raising_cell=None
            )
        )
        assert is_sensitive_error(MarimoSyntaxError(msg=""))
        assert is_sensitive_error(UnknownError(msg=""))
