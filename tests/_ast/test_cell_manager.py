from __future__ import annotations

import pytest

from marimo._ast.cell import Cell, CellConfig
from marimo._ast.cell_manager import CellManager, _match_cell_ids_by_similarity
from marimo._ast.compiler import compile_cell
from marimo._ast.names import DEFAULT_CELL_NAME


@pytest.fixture
def cell_manager():
    return CellManager(prefix="test_")


def test_create_cell_id(cell_manager: CellManager) -> None:
    # Test deterministic behavior with fixed seed
    cell_id1 = cell_manager.create_cell_id()
    cell_id2 = cell_manager.create_cell_id()

    assert cell_id1.startswith("test_")
    assert len(cell_id1) == 9  # "test_" + 4 random letters
    assert cell_id1 != cell_id2


def test_register_cell(cell_manager: CellManager) -> None:
    cell_id = "test_cell"
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


def test_register_cell_auto_id(cell_manager: CellManager) -> None:
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


def test_ensure_one_cell(cell_manager: CellManager) -> None:
    assert len(list(cell_manager.cell_ids())) == 0
    cell_manager.ensure_one_cell()
    assert len(list(cell_manager.cell_ids())) == 1

    # Calling again shouldn't add another cell
    cell_manager.ensure_one_cell()
    assert len(list(cell_manager.cell_ids())) == 1


def test_cell_queries(cell_manager: CellManager) -> None:
    cell_id1 = "test_cell1"
    cell_id2 = "test_cell2"
    code1 = "print('hello')"
    code2 = "print('world')"
    config1 = CellConfig(column=1)
    config2 = CellConfig(disabled=True)

    cell_manager.register_cell(cell_id1, code1, config1, name="cell1")
    cell_manager.register_cell(cell_id2, code2, config2, name="cell2")

    assert list(cell_manager.names()) == ["cell1", "cell2"]
    assert list(cell_manager.codes()) == [code1, code2]
    assert list(cell_manager.configs()) == [config1, config2]
    assert list(cell_manager.cell_ids()) == [cell_id1, cell_id2]
    assert cell_manager.config_map() == {cell_id1: config1, cell_id2: config2}


def test_get_cell_id_by_code(cell_manager: CellManager) -> None:
    code = "print('unique')"
    cell_manager.register_cell("test_cell1", code, CellConfig())
    cell_manager.register_cell("test_cell2", "different_code", CellConfig())

    assert cell_manager.get_cell_id_by_code(code) == "test_cell1"
    assert cell_manager.get_cell_id_by_code("nonexistent") is None


def test_register_unparsable_cell(cell_manager: CellManager) -> None:
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


def test_valid_cells(cell_manager: CellManager) -> None:
    # Register a mix of valid and invalid cells
    cell1 = Cell(_name="_", _cell=compile_cell("print('valid')", "test_cell1"))
    cell_manager.register_cell(
        "test_cell1", "print('valid')", CellConfig(), cell=cell1
    )
    cell_manager.register_cell(
        "test_cell2", "print('invalid')", CellConfig(), cell=None
    )

    valid_cells = list(cell_manager.valid_cells())
    assert len(valid_cells) == 1
    assert valid_cells[0][0] == "test_cell1"
    assert valid_cells[0][1] == cell1

    valid_ids = list(cell_manager.valid_cell_ids())
    assert valid_ids == ["test_cell1"]


def test_match_cell_ids_by_similarity():
    # Test exact matches
    assert _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["abc", "def", "ghi"],
        next_ids=["unused_a", "unused_b", "unused_c"],
        next_codes=["abc", "def", "ghi"],
    ) == ["a", "b", "c"]

    # Test with reordered codes
    assert _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["abc", "def", "ghi"],
        next_ids=["unused_a", "unused_b", "unused_c"],
        next_codes=["def", "ghi", "abc"],
    ) == ["b", "c", "a"]

    # Test with similar but not exact matches
    assert _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["abc", "def", "ghi"],
        next_ids=["unused_a", "unused_b", "unused_c"],
        next_codes=["ghij", "abcd", "defg"],
    ) == ["c", "a", "b"]

    # Test with fewer next cells
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["abc", "def", "ghi"],
        next_ids=["unused_a", "unused_b"],
        next_codes=["abc", "ghi"],
    )
    assert len(result) == 2
    assert result == ["a", "c"]

    # Test with more next cells
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["abc", "def"],
        next_ids=["a", "b", "c"],
        next_codes=["def", "ghi", "abc"],
    )
    assert len(result) == 3
    assert result == ["b", "c", "a"]

    # Test with completely different codes
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["abc", "def"],
        next_ids=["unused_a", "unused_b"],
        next_codes=["xyz", "123"],
    )
    assert len(result) == 2

    # Test empty lists
    assert _match_cell_ids_by_similarity([], [], [], []) == []

    # Test with empty strings
    assert _match_cell_ids_by_similarity(
        prev_ids=["a"],
        prev_codes=[""],
        next_ids=["unused_a"],
        next_codes=[""],
    ) == ["a"]


def test_match_cell_ids_by_similarity_edge_cases():
    # Test with multiple identical codes in prev
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["same", "same", "diff"],
        next_ids=["x", "y"],
        next_codes=["same", "diff"],
    )
    assert len(result) == 2
    assert result[0] in ["a", "b"]
    assert result[1] == "c"

    # Test with multiple identical codes in next
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["code1", "code2"],
        next_ids=["x", "y", "z"],
        next_codes=["code1", "code1", "code2"],
    )
    assert len(result) == 3
    assert result == ["a", "x", "b"]

    # Test with very long common prefixes/suffixes
    long_prefix = "x" * 1000
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=[long_prefix + "1", long_prefix + "2"],
        next_ids=["x", "y"],
        next_codes=[long_prefix + "2", long_prefix + "1"],
    )
    assert result == ["b", "a"]

    # Test with Unicode and special characters
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["🔥", "∑∫", "\n\t\r"],
        next_ids=["x", "y", "z"],
        next_codes=["∑∫", "🔥", "\n\t\r"],
    )
    assert result == ["b", "a", "c"]

    # Test with mixed case sensitivity
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["ABC", "def"],
        next_ids=["x", "y"],
        next_codes=["abc", "DEF"],
    )
    assert len(result) == 2

    # Test with whitespace variations
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["x  y", "a\nb"],
        next_ids=["x", "y"],
        next_codes=["x y", "a b"],
    )
    assert result == ["a", "b"]

    # Test with all codes being substrings of each other
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["x", "xy", "xyz"],
        next_ids=["p", "q", "r"],
        next_codes=["xyz", "xy", "x"],
    )
    assert result == ["c", "b", "a"]

    # Test with maximum length differences
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["x", "x" * 10000],
        next_ids=["y", "z"],
        next_codes=["x" * 10000, "x"],
    )
    assert result == ["b", "a"]

    # Test with empty strings
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["", "x"],
        next_ids=["y", "z"],
        next_codes=["x", ""],
    )
    assert result == ["b", "a"]

    # Test with identical codes
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b", "c"],
        prev_codes=["same", "same", "same"],
        next_ids=["x", "y", "z"],
        next_codes=["same", "same", "same"],
    )
    assert len(result) == 3
    assert set(result) == {"a", "b", "c"}

    # Test with completely different codes
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["abc", "def"],
        next_ids=["x", "y"],
        next_codes=["123", "456"],
    )
    assert len(result) == 2
    # This is probably ok since they are completely different.
    # Not sure what the best behavior is.
    assert result == ["b", "x"]

    # Test with special Python syntax
    result = _match_cell_ids_by_similarity(
        prev_ids=["a", "b"],
        prev_codes=["def foo():", "class Bar:"],
        next_ids=["x", "y"],
        next_codes=["class Bar:", "def foo():"],
    )
    assert result == ["b", "a"]


def test_sort_cell_ids_by_similarity_reorder():
    # Test simple reorder
    prev_manager = CellManager()
    prev_manager.register_cell("a", "code1", CellConfig())
    prev_manager.register_cell("b", "code2", CellConfig())

    curr_manager = CellManager()
    curr_manager.register_cell("x", "code2", CellConfig())
    curr_manager.register_cell("y", "code1", CellConfig())

    # Save original seen_ids
    original_seen_ids = curr_manager.seen_ids.copy()

    curr_manager.sort_cell_ids_by_similarity(prev_manager)
    assert list(curr_manager.cell_ids()) == ["b", "a"]
    assert curr_manager.cell_data_at("b").code == "code2"
    assert curr_manager.cell_data_at("a").code == "code1"

    # Check seen_ids were updated
    assert curr_manager.seen_ids == original_seen_ids | {"a", "b"}


def test_sort_cell_ids_by_similarity_reorder_same_ids():
    # Test simple reorder
    prev_manager = CellManager()
    prev_manager.register_cell("a", "code1", CellConfig())
    prev_manager.register_cell("b", "code2", CellConfig())

    curr_manager = CellManager()
    curr_manager.register_cell("a", "code2", CellConfig())
    curr_manager.register_cell("b", "code1", CellConfig())

    # Save original seen_ids
    original_seen_ids = curr_manager.seen_ids.copy()

    curr_manager.sort_cell_ids_by_similarity(prev_manager)
    assert list(curr_manager.cell_ids()) == ["b", "a"]
    assert curr_manager.cell_data_at("b").code == "code2"
    assert curr_manager.cell_data_at("a").code == "code1"

    # Check seen_ids were updated
    assert curr_manager.seen_ids == original_seen_ids | {"a", "b"}


def test_sort_cell_ids_by_similarity_less_cells():
    # Test less cells than before
    prev_manager = CellManager()
    prev_manager.register_cell("a", "code1", CellConfig())
    prev_manager.register_cell("b", "code2", CellConfig())
    prev_manager.register_cell("c", "code3", CellConfig())

    curr_manager = CellManager()
    curr_manager.register_cell("x", "code2", CellConfig())
    curr_manager.register_cell("y", "code1", CellConfig())

    original_seen_ids = curr_manager.seen_ids.copy()

    curr_manager.sort_cell_ids_by_similarity(prev_manager)
    assert list(curr_manager.cell_ids()) == ["b", "a"]
    assert curr_manager.seen_ids == original_seen_ids | {"a", "b"}
    assert curr_manager.cell_data_at("b").code == "code2"
    assert curr_manager.cell_data_at("a").code == "code1"


def test_sort_cell_ids_by_similarity_more_cells():
    # Test more cells than before
    prev_manager = CellManager()
    prev_manager.register_cell("a", "code1", CellConfig())
    prev_manager.register_cell("b", "code2", CellConfig())

    curr_manager = CellManager()
    curr_manager.register_cell("x", "code2", CellConfig())
    curr_manager.register_cell("y", "code1", CellConfig())
    curr_manager.register_cell("z", "code3", CellConfig())

    original_seen_ids = curr_manager.seen_ids.copy()

    curr_manager.sort_cell_ids_by_similarity(prev_manager)
    assert list(curr_manager.cell_ids()) == ["b", "a", "x"]
    assert curr_manager.seen_ids == original_seen_ids | {"a", "b", "x"}
    assert curr_manager.cell_data_at("b").code == "code2"
    assert curr_manager.cell_data_at("a").code == "code1"
    assert curr_manager.cell_data_at("x").code == "code3"
