from __future__ import annotations

from unittest.mock import patch

import pytest

from marimo._ast.cell import Cell, CellConfig
from marimo._ast.cell_manager import (
    CellManager,
)
from marimo._ast.compiler import compile_cell
from marimo._ast.names import DEFAULT_CELL_NAME
from marimo._types.ids import CellId_t
from marimo._utils.cell_matching import _match_cell_ids_by_similarity

# Test cell ID constants
CELL_A = CellId_t("a")
CELL_B = CellId_t("b")
CELL_C = CellId_t("c")
CELL_X = CellId_t("x")
CELL_Y = CellId_t("y")
CELL_Z = CellId_t("z")
CELL_P = CellId_t("p")
CELL_Q = CellId_t("q")
CELL_R = CellId_t("r")
TEST_CELL1 = CellId_t("test_cell1")
TEST_CELL2 = CellId_t("test_cell2")
UNUSED_A = CellId_t("unused_a")
UNUSED_B = CellId_t("unused_b")
UNUSED_C = CellId_t("unused_c")
UNUSED_X = CellId_t("unused_x")
UNUSED_Y = CellId_t("unused_y")
UNUSED_Z = CellId_t("unused_z")


@pytest.fixture
def cell_manager():
    return CellManager(prefix="test_")


class TestCellManager:
    """Test class for CellManager functionality."""

    def test_create_cell_id(self, cell_manager: CellManager) -> None:
        # Test deterministic behavior with fixed seed
        cell_id1 = cell_manager.create_cell_id()
        cell_id2 = cell_manager.create_cell_id()

        assert cell_id1.startswith("test_")
        assert len(cell_id1) == 9  # "test_" + 4 random letters
        assert cell_id1 != cell_id2

    def test_register_cell(self, cell_manager: CellManager) -> None:
        cell_id = CellId_t("test_cell")
        code = "print('hello')"
        config = CellConfig()

        cell_manager.register_cell(
            cell_id=cell_id,
            code=code,
            config=config,
            name=DEFAULT_CELL_NAME,
        )

        assert cell_manager.has_cell(cell_id)
        cell_data = cell_manager.cell_data_at(cell_id)
        assert cell_data.code == code
        assert cell_data.config == config
        assert cell_data.name == DEFAULT_CELL_NAME

    def test_register_cell_auto_id(self, cell_manager: CellManager) -> None:
        code = "print('hello')"
        config = CellConfig()

        cell_manager.register_cell(
            cell_id=None,
            code=code,
            config=config,
        )

        # Should have created one cell with an auto-generated ID
        assert len(list(cell_manager.cell_ids())) == 1
        cell_id = next(iter(cell_manager.cell_ids()))
        assert cell_id.startswith("test_")

    def test_ensure_one_cell(self, cell_manager: CellManager) -> None:
        assert len(list(cell_manager.cell_ids())) == 0
        cell_manager.ensure_one_cell()
        assert len(list(cell_manager.cell_ids())) == 1

        # Calling again shouldn't add another cell
        cell_manager.ensure_one_cell()
        assert len(list(cell_manager.cell_ids())) == 1

    def test_cell_queries(self, cell_manager: CellManager) -> None:
        code1 = "print('hello')"
        code2 = "print('world')"
        config1 = CellConfig(column=1)
        config2 = CellConfig(disabled=True)

        cell_manager.register_cell(TEST_CELL1, code1, config1, name="cell1")
        cell_manager.register_cell(TEST_CELL2, code2, config2, name="cell2")

        assert list(cell_manager.names()) == ["cell1", "cell2"]
        assert list(cell_manager.codes()) == [code1, code2]
        assert list(cell_manager.configs()) == [config1, config2]
        assert list(cell_manager.cell_ids()) == [TEST_CELL1, TEST_CELL2]
        assert cell_manager.config_map() == {
            TEST_CELL1: config1,
            TEST_CELL2: config2,
        }

    def test_get_cell_id_by_code(self, cell_manager: CellManager) -> None:
        code = "print('unique')"
        cell_manager.register_cell(TEST_CELL1, code, CellConfig())
        cell_manager.register_cell(TEST_CELL2, "different_code", CellConfig())

        assert cell_manager.get_cell_id_by_code(code) == TEST_CELL1
        assert cell_manager.get_cell_id_by_code("nonexistent") is None

    def test_get_cell_code(self, cell_manager: CellManager) -> None:
        code = "print('hello')"
        cell_manager.register_cell(TEST_CELL1, code, CellConfig())
        assert cell_manager.get_cell_code(TEST_CELL1) == code
        assert cell_manager.get_cell_code(CellId_t("nonexistent")) is None

    def test_get_cell_data(self, cell_manager: CellManager) -> None:
        code = "print('hello')"
        config = CellConfig(column=1, disabled=True)
        name = "test_cell"

        cell_manager.register_cell(TEST_CELL1, code, config, name=name)

        # Test getting existing cell data
        cell_data = cell_manager.get_cell_data(TEST_CELL1)
        assert cell_data is not None
        assert cell_data.cell_id == TEST_CELL1
        assert cell_data.code == code
        assert cell_data.config == config
        assert cell_data.name == name

        # Test getting non-existent cell data
        assert cell_manager.get_cell_data(CellId_t("nonexistent")) is None

    def test_register_unparsable_cell(self, cell_manager: CellManager) -> None:
        code = """
        def unparsable():
            return "test"
        """
        config = CellConfig()

        cell_manager.register_unparsable_cell(
            code=code,
            name="unparsable",
            cell_config=config,
        )

        cell_data = next(iter(cell_manager.cell_data()))
        assert cell_data.name == "unparsable"
        assert "def unparsable():" in cell_data.code
        assert cell_data.cell is None  # Unparsable cells have no Cell object

    def test_valid_cells(self, cell_manager: CellManager) -> None:
        # Register a mix of valid and invalid cells
        cell1 = Cell(
            _name="_", _cell=compile_cell("print('valid')", TEST_CELL1)
        )
        cell_manager.register_cell(
            TEST_CELL1, "print('valid')", CellConfig(), cell=cell1
        )
        cell_manager.register_cell(
            TEST_CELL2, "print('invalid')", CellConfig(), cell=None
        )

        valid_cells = list(cell_manager.valid_cells())
        assert len(valid_cells) == 1
        assert valid_cells[0][0] == TEST_CELL1
        assert valid_cells[0][1] == cell1

        valid_ids = list(cell_manager.valid_cell_ids())
        assert valid_ids == [TEST_CELL1]

    def test_create_cell_id_1000(self) -> None:
        manager = CellManager()
        ids: set[CellId_t] = set()
        for _ in range(1000):
            ids.add(manager.create_cell_id())
        assert len(ids) == 1000

    def test_create_cell_passes_filename(
        self, cell_manager: CellManager
    ) -> None:
        """Test that create_cell passes filename to ir_cell_factory."""
        from marimo._ast.app import App

        app = App()
        app._filename = "test_notebook.py"

        # Mock ir_cell_factory to capture the filename parameter
        with patch(
            "marimo._ast.compiler.ir_cell_factory"
        ) as mock_ir_cell_factory:
            mock_ir_cell_factory.return_value = Cell(
                _name="test", _cell=compile_cell("x = 1", TEST_CELL1)
            )

            cell_manager.create_cell(
                cell_def={"code": "x = 1", "options": {}}, app=app
            )

            # Verify ir_cell_factory was called with filename
            mock_ir_cell_factory.assert_called_once()
            call_args = mock_ir_cell_factory.call_args
            assert call_args[1]["filename"] == "test_notebook.py"

    def test_create_cell_no_filename_when_app_none(
        self, cell_manager: CellManager
    ) -> None:
        """Test that create_cell passes None filename when app is None."""
        with patch(
            "marimo._ast.compiler.ir_cell_factory"
        ) as mock_ir_cell_factory:
            mock_ir_cell_factory.return_value = Cell(
                _name="test", _cell=compile_cell("x = 1", TEST_CELL1)
            )

            cell_manager.create_cell(
                cell_def={"code": "x = 1", "options": {}}, app=None
            )

            # Verify ir_cell_factory was called with None filename
            mock_ir_cell_factory.assert_called_once()
            call_args = mock_ir_cell_factory.call_args
            assert call_args[1]["filename"] is None


class TestCellMatching:
    """Test class for cell matching functionality."""

    def test_exact_matches(self) -> None:
        """Test exact code matches."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["abc", "def", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C],
            next_codes=["abc", "def", "ghi"],
        )
        assert result == [CELL_A, CELL_B, CELL_C]

    def test_reordered_codes(self) -> None:
        """Test with reordered codes."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["abc", "def", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C],
            next_codes=["def", "ghi", "abc"],
        )
        assert result == [CELL_B, CELL_C, CELL_A]

    def test_similar_but_not_exact_matches(self) -> None:
        """Test with similar but not exact matches."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["abc", "def", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C],
            next_codes=["ghij", "abcd", "defg"],
        )
        assert result == [CELL_C, CELL_A, CELL_B]

    def test_similar_but_not_exact_matches_with_dupes(self) -> None:
        """Test with similar but not exact matches and duplicates."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C, CELL_X],
            prev_codes=["abc", "def", "ghi", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C, UNUSED_X],
            next_codes=["ghij", "abcd", "defg", "ghij"],
        )
        assert result == [CELL_C, CELL_A, CELL_B, CELL_X]

    def test_left_inexact_matches_with_dupes(self) -> None:
        """Test left inexact matches and duplicates."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["abc", "def", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C, CELL_X],
            next_codes=["ghij", "abcd", "defg", "ghij"],
        )
        assert result == [CELL_C, CELL_A, CELL_B, CELL_X]

    def test_right_inexact_matches_with_dupes(self) -> None:
        """Test right inexact matches and duplicates."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C, CELL_X],
            prev_codes=["abc", "def", "ghi", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C],
            next_codes=["ghij", "abcd", "defg"],
        )
        assert result == [CELL_C, CELL_A, CELL_B]

    def test_outer_inexact_matches(self) -> None:
        """Test outer inexact matches and duplicates."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C, CELL_X],
            prev_codes=["abc", "def", "ghi", "123"],
            next_ids=[UNUSED_A, UNUSED_B, UNUSED_C, UNUSED_X],
            next_codes=["ghij", "abcd", "defg", "abc"],
        )
        assert result == [CELL_C, CELL_X, CELL_B, CELL_A]

    def test_outer_inexact_matches_with_dupes(self) -> None:
        """Test outer inexact matches and duplicates."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C, CELL_X, CELL_Y, CELL_Z],
            prev_codes=["abc", "def", "ghi", "def", "abc", "123"],
            next_ids=[
                UNUSED_A,
                UNUSED_B,
                UNUSED_C,
                UNUSED_X,
                UNUSED_Y,
                UNUSED_Z,
            ],
            next_codes=["ghij", "abcd", "defg", "defg", "ghij", "abc"],
        )
        # NB. Locality given preference when dequeuing dupes.
        assert result == [CELL_C, CELL_A, CELL_B, CELL_X, CELL_Z, CELL_Y]

    def test_fewer_next_cells(self) -> None:
        """Test with fewer next cells than previous."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["abc", "def", "ghi"],
            next_ids=[UNUSED_A, UNUSED_B],
            next_codes=["abc", "ghi"],
        )
        assert len(result) == 2
        assert result == [CELL_A, CELL_C]

    def test_more_next_cells(self) -> None:
        """Test with more next cells than previous."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["abc", "def"],
            next_ids=[CELL_A, CELL_B, CELL_C],
            next_codes=["def", "ghi", "abc"],
        )
        assert len(result) == 3
        assert result == [CELL_B, CELL_C, CELL_A]

    def test_completely_different_codes(self) -> None:
        """Test with completely different codes."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["abc", "def"],
            next_ids=[UNUSED_A, UNUSED_B],
            next_codes=["xyz", "123"],
        )
        assert len(result) == 2

    def test_empty_lists(self) -> None:
        """Test with empty lists."""
        assert _match_cell_ids_by_similarity([], [], [], []) == []

    def test_empty_strings(self) -> None:
        """Test with empty strings."""
        assert _match_cell_ids_by_similarity(
            prev_ids=[CELL_A],
            prev_codes=[""],
            next_ids=[UNUSED_A],
            next_codes=[""],
        ) == [CELL_A]


class TestCellMatchingEdgeCases:
    """Test class for edge cases in cell matching."""

    def test_multiple_identical_codes_in_prev(self) -> None:
        """Test with multiple identical codes in previous cells."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["same", "same", "diff"],
            next_ids=[CELL_X, CELL_Y],
            next_codes=["same", "diff"],
        )
        assert len(result) == 2
        assert result[0] in [CELL_A, CELL_B]
        assert result[1] == CELL_C

    def test_multiple_identical_codes_in_next(self) -> None:
        """Test with multiple identical codes in next cells."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["code1", "code2"],
            next_ids=[CELL_X, CELL_Y, CELL_Z],
            next_codes=["code1", "code1", "code2"],
        )
        assert len(result) == 3
        assert result == [CELL_A, CELL_Y, CELL_B]

    def test_very_long_common_prefixes_suffixes(self) -> None:
        """Test with very long common prefixes/suffixes."""
        long_prefix = "x" * 1000
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=[long_prefix + "1", long_prefix + "2"],
            next_ids=[CELL_X, CELL_Y],
            next_codes=[long_prefix + "2", long_prefix + "1"],
        )
        assert result == [CELL_B, CELL_A]

    def test_unicode_and_special_characters(self) -> None:
        """Test with Unicode and special characters."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["🔥", "∑∫", "\n\t\r"],
            next_ids=[CELL_X, CELL_Y, CELL_Z],
            next_codes=["∑∫", "🔥", "\n\t\r"],
        )
        assert result == [CELL_B, CELL_A, CELL_C]

    def test_mixed_case_sensitivity(self) -> None:
        """Test with mixed case sensitivity."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["ABC", "def"],
            next_ids=[CELL_X, CELL_Y],
            next_codes=["abc", "DEF"],
        )
        assert result == [CELL_A, CELL_B]

    def test_whitespace_variations(self) -> None:
        """Test with whitespace variations."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["x  y", "a\nb"],
            next_ids=[CELL_X, CELL_Y],
            next_codes=["x y", "a b"],
        )
        assert result == [CELL_A, CELL_B]

    def test_all_codes_being_substrings(self) -> None:
        """Test with all codes being substrings of each other."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["x", "xy", "xyz"],
            next_ids=[CELL_P, CELL_Q, CELL_R],
            next_codes=["xyz", "xy", "x"],
        )
        assert result == [CELL_C, CELL_B, CELL_A]

    def test_maximum_length_differences(self) -> None:
        """Test with maximum length differences."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["x", "x" * 10000],
            next_ids=[CELL_Y, CELL_Z],
            next_codes=["x" * 10000, "x"],
        )
        assert result == [CELL_B, CELL_A]

    def test_empty_strings_edge_case(self) -> None:
        """Test with empty strings edge case."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["", "x"],
            next_ids=[CELL_Y, CELL_Z],
            next_codes=["x", ""],
        )
        assert result == [CELL_B, CELL_A]

    def test_identical_codes(self) -> None:
        """Test with identical codes."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B, CELL_C],
            prev_codes=["same", "same", "same"],
            next_ids=[CELL_X, CELL_Y, CELL_Z],
            next_codes=["same", "same", "same"],
        )
        assert len(result) == 3
        assert set(result) == {CELL_A, CELL_B, CELL_C}

    def test_completely_different_codes_edge_case(self) -> None:
        """Test with completely different codes edge case."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["abc", "def"],
            next_ids=[CELL_X, CELL_Y],
            next_codes=["123", "456"],
        )
        assert len(result) == 2
        assert result == [CELL_A, CELL_B]

    def test_special_python_syntax(self) -> None:
        """Test with special Python syntax."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["def foo():", "class Bar:"],
            next_ids=[CELL_X, CELL_Y],
            next_codes=["class Bar:", "def foo():"],
        )
        assert result == [CELL_B, CELL_A]

    def test_similar_reduction(self) -> None:
        """test with similar and reduction."""
        result = _match_cell_ids_by_similarity(
            prev_ids=[CELL_A, CELL_B],
            prev_codes=["y = x + 1", "x = 1"],
            next_ids=[CELL_A],
            next_codes=["y = 2 + 1"],
        )
        assert len(result) == 1
        assert result == [CELL_A]


class TestSortCellIdsBySimilarity:
    """Test class for sorting cell IDs by similarity."""

    def test_simple_reorder(self) -> None:
        """Test simple reorder."""
        prev_manager = CellManager()
        prev_manager.register_cell(CELL_A, "code1", CellConfig())
        prev_manager.register_cell(CELL_B, "code2", CellConfig())

        curr_manager = CellManager()
        curr_manager.register_cell(CELL_X, "code2", CellConfig())
        curr_manager.register_cell(CELL_Y, "code1", CellConfig())

        # Save original seen_ids
        original_seen_ids = curr_manager.seen_ids.copy()

        curr_manager.sort_cell_ids_by_similarity(prev_manager)
        assert list(curr_manager.cell_ids()) == [CELL_B, CELL_A]
        assert curr_manager.cell_data_at(CELL_B).code == "code2"
        assert curr_manager.cell_data_at(CELL_A).code == "code1"

        # Check seen_ids were updated
        assert curr_manager.seen_ids == original_seen_ids | {CELL_A, CELL_B}

    def test_reorder_same_ids(self) -> None:
        """Test reorder with same IDs."""
        prev_manager = CellManager()
        prev_manager.register_cell(CELL_A, "code1", CellConfig())
        prev_manager.register_cell(CELL_B, "code2", CellConfig())

        curr_manager = CellManager()
        curr_manager.register_cell(CELL_A, "code2", CellConfig())
        curr_manager.register_cell(CELL_B, "code1", CellConfig())

        # Save original seen_ids
        original_seen_ids = curr_manager.seen_ids.copy()

        curr_manager.sort_cell_ids_by_similarity(prev_manager)
        assert list(curr_manager.cell_ids()) == [CELL_B, CELL_A]
        assert curr_manager.cell_data_at(CELL_B).code == "code2"
        assert curr_manager.cell_data_at(CELL_A).code == "code1"

        # Check seen_ids were updated
        assert curr_manager.seen_ids == original_seen_ids | {CELL_A, CELL_B}

    def test_less_cells(self) -> None:
        """Test with fewer cells than before."""
        prev_manager = CellManager()
        prev_manager.register_cell(CELL_A, "code1", CellConfig())
        prev_manager.register_cell(CELL_B, "code2", CellConfig())
        prev_manager.register_cell(CELL_C, "code3", CellConfig())

        curr_manager = CellManager()
        curr_manager.register_cell(CELL_X, "code2", CellConfig())
        curr_manager.register_cell(CELL_Y, "code1", CellConfig())

        original_seen_ids = curr_manager.seen_ids.copy()

        curr_manager.sort_cell_ids_by_similarity(prev_manager)
        assert list(curr_manager.cell_ids()) == [CELL_B, CELL_A]
        assert curr_manager.seen_ids == original_seen_ids | {CELL_A, CELL_B}
        assert curr_manager.cell_data_at(CELL_B).code == "code2"
        assert curr_manager.cell_data_at(CELL_A).code == "code1"

    def test_more_cells(self) -> None:
        """Test with more cells than before."""
        prev_manager = CellManager()
        prev_manager.register_cell(CELL_A, "code1", CellConfig())
        prev_manager.register_cell(CELL_B, "code2", CellConfig())

        curr_manager = CellManager()
        curr_manager.register_cell(CELL_X, "code2", CellConfig())
        curr_manager.register_cell(CELL_Y, "code1", CellConfig())
        curr_manager.register_cell(CELL_Z, "code3", CellConfig())

        original_seen_ids = curr_manager.seen_ids.copy()

        curr_manager.sort_cell_ids_by_similarity(prev_manager)
        assert list(curr_manager.cell_ids()) == [CELL_B, CELL_A, CELL_Z]
        assert curr_manager.seen_ids == original_seen_ids | {
            CELL_A,
            CELL_B,
            CELL_Z,
        }
        assert curr_manager.cell_data_at(CELL_B).code == "code2"
        assert curr_manager.cell_data_at(CELL_A).code == "code1"
        assert curr_manager.cell_data_at(CELL_Z).code == "code3"

    def test_similar_reduction(self) -> None:
        # Same as above but using CellManager
        prev_manager = CellManager()
        prev_manager.register_cell(CELL_A, "y = x + 1", CellConfig())
        prev_manager.register_cell(CELL_B, "x = 1", CellConfig())
        curr_manager = CellManager()
        curr_manager.register_cell(CELL_A, "y = 2 + 1", CellConfig())
        original_seen_ids = curr_manager.seen_ids.copy()
        curr_manager.sort_cell_ids_by_similarity(prev_manager)
        assert list(curr_manager.cell_ids()) == [CELL_A]
        assert curr_manager.seen_ids == {CELL_A}
        assert curr_manager.cell_data_at(CELL_A).code == "y = 2 + 1"
