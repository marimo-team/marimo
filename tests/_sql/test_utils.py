# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal
from unittest.mock import Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.utils import convert_to_output

native_result = {"data": "native_result"}
polars_result = {"data": "polars_result"}
pandas_result = {"data": "pandas_result"}
lazy_polars_result = {"data": "lazy_polars_result"}


MockFunctions = Literal[
    "to_native", "to_polars", "to_pandas", "to_lazy_polars"
]
MockFnDict = dict[MockFunctions, Mock]


@pytest.fixture
def mock_functions() -> MockFnDict:
    """Returns a dictionary of mock conversion functions keyed by their names."""
    return {
        "to_native": Mock(return_value=native_result),
        "to_polars": Mock(return_value=polars_result),
        "to_pandas": Mock(return_value=pandas_result),
        "to_lazy_polars": Mock(return_value=lazy_polars_result),
    }


def assert_only_one_called(
    mock_functions: MockFnDict, function_name: MockFunctions
) -> None:
    """Assert that only the specified mock function was called."""
    for name, mock_fn in mock_functions.items():
        if name == function_name:
            mock_fn.assert_called_once()
        else:
            mock_fn.assert_not_called()


def assert_multiple_called_once(
    mock_functions: MockFnDict, expected_called: list[MockFunctions]
) -> None:
    """Assert that only the specified mock functions were called once each."""
    for name, mock_fn in mock_functions.items():
        if name in expected_called:
            mock_fn.assert_called_once()
        else:
            mock_fn.assert_not_called()


class TestNativeOutputFormat:
    """Test native output format scenarios."""

    def test_with_to_native(self, mock_functions: MockFnDict) -> None:
        """Test native output format when to_native is provided."""
        result = convert_to_output(
            sql_output_format="native",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
            to_native=mock_functions["to_native"],
        )

        assert result == native_result
        assert_only_one_called(mock_functions, "to_native")

    def test_without_to_native(self, mock_functions: MockFnDict) -> None:
        """Test native output format when to_native is not provided."""
        with pytest.raises(
            ValueError, match="to_native is required for native output format"
        ):
            convert_to_output(
                sql_output_format="native",
                to_polars=mock_functions["to_polars"],
                to_pandas=mock_functions["to_pandas"],
            )


class TestPolarsOutputFormat:
    """Test polars output format scenarios."""

    @pytest.mark.skipif(
        not DependencyManager.polars.has(),
        reason="Polars is not installed",
    )
    def test_polars_format(self, mock_functions: MockFnDict) -> None:
        """Test polars output format."""
        result = convert_to_output(
            sql_output_format="polars",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == polars_result
        assert_only_one_called(mock_functions, "to_polars")


@pytest.mark.skipif(
    not DependencyManager.polars.has(),
    reason="Polars is not installed",
)
class TestLazyPolarsOutputFormat:
    """Test lazy-polars output format scenarios."""

    def test_with_to_lazy_polars(self, mock_functions: MockFnDict) -> None:
        """Test lazy-polars output format when to_lazy_polars is provided."""
        result = convert_to_output(
            sql_output_format="lazy-polars",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
            to_lazy_polars=mock_functions["to_lazy_polars"],
        )

        assert result == lazy_polars_result
        assert_only_one_called(mock_functions, "to_lazy_polars")

    def test_without_to_lazy_polars_dataframe(
        self, mock_functions: MockFnDict
    ) -> None:
        """Test lazy-polars output format when to_lazy_polars is not provided and to_polars returns DataFrame."""
        mock_dataframe = Mock()
        mock_lazy_frame = Mock()
        mock_dataframe.lazy.return_value = mock_lazy_frame
        mock_functions["to_polars"].return_value = mock_dataframe

        result = convert_to_output(
            sql_output_format="lazy-polars",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == mock_lazy_frame
        mock_functions["to_polars"].assert_called_once()
        mock_dataframe.lazy.assert_called_once()
        mock_functions["to_pandas"].assert_not_called()

    def test_without_to_lazy_polars_series(
        self, mock_functions: MockFnDict
    ) -> None:
        """Test lazy-polars output format when to_lazy_polars is not provided and to_polars returns Series."""
        import polars as pl

        mock_series = Mock(spec=pl.Series)
        mock_frame = Mock()
        mock_lazy_frame = Mock()
        mock_series.to_frame.return_value = mock_frame
        mock_frame.lazy.return_value = mock_lazy_frame
        mock_functions["to_polars"].return_value = mock_series

        result = convert_to_output(
            sql_output_format="lazy-polars",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == mock_lazy_frame
        mock_functions["to_polars"].assert_called_once()
        mock_series.to_frame.assert_called_once()
        mock_frame.lazy.assert_called_once()
        mock_functions["to_pandas"].assert_not_called()


@pytest.mark.skipif(
    not DependencyManager.pandas.has(),
    reason="Pandas is not installed",
)
class TestPandasOutputFormat:
    """Test pandas output format scenarios."""

    def test_pandas_format(self, mock_functions: MockFnDict) -> None:
        """Test pandas output format."""
        result = convert_to_output(
            sql_output_format="pandas",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == pandas_result
        assert_only_one_called(mock_functions, "to_pandas")


class TestAutoOutputFormat:
    """Test auto output format scenarios."""

    @pytest.mark.skipif(
        not DependencyManager.polars.has(),
        reason="Polars is not installed",
    )
    @patch("marimo._sql.utils.DependencyManager")
    def test_with_polars_success(
        self, mock_dependency_manager: Mock, mock_functions: MockFnDict
    ) -> None:
        """Test auto output format when polars is available and succeeds."""
        mock_dependency_manager.polars.has.return_value = True
        mock_dependency_manager.pandas.has.return_value = False

        result = convert_to_output(
            sql_output_format="auto",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == polars_result
        assert_only_one_called(mock_functions, "to_polars")

    @pytest.mark.skipif(
        not DependencyManager.polars.has(),
        reason="Polars is not installed",
    )
    @patch("marimo._sql.utils.DependencyManager")
    @patch("marimo._sql.utils.LOGGER")
    def test_with_polars_failure_fallback_to_pandas(
        self,
        mock_logger: Mock,
        mock_dependency_manager: Mock,
        mock_functions: MockFnDict,
    ) -> None:
        """Test auto output format when polars fails and falls back to pandas."""
        mock_dependency_manager.polars.has.return_value = True
        mock_dependency_manager.pandas.has.return_value = True

        import polars as pl

        mock_functions["to_polars"].side_effect = pl.exceptions.PanicException(
            "test error"
        )

        result = convert_to_output(
            sql_output_format="auto",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == pandas_result
        assert_multiple_called_once(mock_functions, ["to_polars", "to_pandas"])
        mock_logger.info.assert_called_once_with(
            "Failed to convert to polars, falling back to pandas"
        )

    @pytest.mark.skipif(
        not DependencyManager.polars.has(),
        reason="Polars is not installed",
    )
    @patch("marimo._sql.utils.DependencyManager")
    @patch("marimo._sql.utils.LOGGER")
    def test_with_polars_compute_error_fallback_to_pandas(
        self,
        mock_logger: Mock,
        mock_dependency_manager: Mock,
        mock_functions: MockFnDict,
    ) -> None:
        """Test auto output format when polars ComputeError occurs and falls back to pandas."""
        mock_dependency_manager.polars.has.return_value = True
        mock_dependency_manager.pandas.has.return_value = True

        import polars as pl

        mock_functions["to_polars"].side_effect = pl.exceptions.ComputeError(
            "test error"
        )

        result = convert_to_output(
            sql_output_format="auto",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == pandas_result
        assert_multiple_called_once(mock_functions, ["to_polars", "to_pandas"])
        mock_logger.info.assert_called_once_with(
            "Failed to convert to polars, falling back to pandas"
        )

    @patch("marimo._sql.utils.DependencyManager")
    def test_without_polars_with_pandas_success(
        self, mock_dependency_manager: Mock, mock_functions: MockFnDict
    ) -> None:
        """Test auto output format when polars is not available but pandas succeeds."""
        mock_dependency_manager.polars.has.return_value = False
        mock_dependency_manager.pandas.has.return_value = True

        result = convert_to_output(
            sql_output_format="auto",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == pandas_result
        assert_only_one_called(mock_functions, "to_pandas")

    @patch("marimo._sql.utils.DependencyManager")
    @patch("marimo._sql.utils.LOGGER")
    def test_without_polars_with_pandas_failure(
        self,
        mock_logger: Mock,
        mock_dependency_manager: Mock,
        mock_functions: MockFnDict,
    ) -> None:
        """Test auto output format when polars is not available and pandas fails."""
        mock_dependency_manager.polars.has.return_value = False
        mock_dependency_manager.pandas.has.return_value = True

        pandas_error = Exception("pandas error")
        mock_functions["to_pandas"].side_effect = pandas_error

        result = convert_to_output(
            sql_output_format="auto",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result is None
        assert_only_one_called(mock_functions, "to_pandas")
        mock_logger.warning.assert_called_once_with(
            "Failed to convert dataframe", exc_info=pandas_error
        )

    @patch("marimo._sql.utils.DependencyManager")
    def test_without_polars_without_pandas(
        self, mock_dependency_manager: Mock, mock_functions: MockFnDict
    ) -> None:
        """Test auto output format when neither polars nor pandas is available."""
        mock_dependency_manager.polars.has.return_value = False
        mock_dependency_manager.pandas.has.return_value = False

        with pytest.raises(
            ModuleNotFoundError, match="pandas or polars is required"
        ):
            convert_to_output(
                sql_output_format="auto",
                to_polars=mock_functions["to_polars"],
                to_pandas=mock_functions["to_pandas"],
            )

        mock_functions["to_polars"].assert_not_called()
        mock_functions["to_pandas"].assert_not_called()

    @pytest.mark.skipif(
        not DependencyManager.polars.has(),
        reason="Polars is not installed",
    )
    @patch("marimo._sql.utils.DependencyManager")
    def test_with_polars_failure_no_pandas(
        self, mock_dependency_manager: Mock, mock_functions: MockFnDict
    ) -> None:
        """Test auto output format when polars fails and pandas is not available."""
        mock_dependency_manager.polars.has.return_value = True
        mock_dependency_manager.pandas.has.return_value = False

        import polars as pl

        mock_functions["to_polars"].side_effect = pl.exceptions.PanicException(
            "test error"
        )

        with pytest.raises(
            ModuleNotFoundError, match="pandas or polars is required"
        ):
            convert_to_output(
                sql_output_format="auto",
                to_polars=mock_functions["to_polars"],
                to_pandas=mock_functions["to_pandas"],
            )

        mock_functions["to_polars"].assert_called_once()
        mock_functions["to_pandas"].assert_not_called()


class TestAllOutputFormats:
    """Test all output format types."""

    @pytest.mark.skipif(
        not DependencyManager.polars.has()
        and not DependencyManager.pandas.has(),
        reason="Polars and pandas are not installed",
    )
    @pytest.mark.parametrize(
        ("format_type", "expected_result", "expected_called_once"),
        [
            ("polars", polars_result, ["to_polars"]),
            ("pandas", pandas_result, ["to_pandas"]),
            ("native", native_result, ["to_native"]),
            ("lazy-polars", lazy_polars_result, ["to_lazy_polars"]),
        ],
    )
    def test_basic_formats(
        self,
        format_type: str,
        expected_result: dict,
        expected_called_once: list[str],
        mock_functions: MockFnDict,
    ) -> None:
        """Test basic output formats without complex dependencies."""
        result = convert_to_output(
            sql_output_format=format_type,
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
            to_native=mock_functions["to_native"],
            to_lazy_polars=mock_functions["to_lazy_polars"],
        )

        assert result == expected_result
        assert_multiple_called_once(mock_functions, expected_called_once)  # type: ignore

    @pytest.mark.skipif(
        not DependencyManager.polars.has(),
        reason="Polars is not installed",
    )
    @patch("marimo._sql.utils.DependencyManager")
    def test_auto_format_with_polars(
        self, mock_dependency_manager: Mock, mock_functions: MockFnDict
    ) -> None:
        """Test auto format when polars is available."""
        mock_dependency_manager.polars.has.return_value = True
        mock_dependency_manager.pandas.has.return_value = False

        result = convert_to_output(
            sql_output_format="auto",
            to_polars=mock_functions["to_polars"],
            to_pandas=mock_functions["to_pandas"],
        )

        assert result == polars_result
        assert_only_one_called(mock_functions, "to_polars")
