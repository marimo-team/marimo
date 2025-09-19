import pytest

from marimo._utils.keyed_list import KeyedList


class Item:
    def __init__(self, key: str, value: int):
        self.key = key
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, Item):
            return False
        return self.key == other.key and self.value == other.value

    def __repr__(self):
        return f"Item({self.key!r}, {self.value!r})"


@pytest.fixture
def sample_items():
    return [
        Item("a", 1),
        Item("b", 2),
        Item("c", 3),
    ]


@pytest.fixture
def keyed_list(sample_items):
    return KeyedList(sample_items, lambda item: item.key)


class TestKeyedList:
    def test_init(self, sample_items):
        """Test initialization with items and key function."""
        kl = KeyedList(sample_items, lambda item: item.key)
        assert len(kl) == 3

    def test_init_empty(self):
        """Test initialization with empty list."""
        kl = KeyedList([], lambda item: item.key)
        assert len(kl) == 0

    def test_getitem_by_index(self, keyed_list, sample_items):
        """Test accessing items by integer index."""
        assert keyed_list[0] == sample_items[0]
        assert keyed_list[1] == sample_items[1]
        assert keyed_list[2] == sample_items[2]

    def test_getitem_negative_index(self, keyed_list, sample_items):
        """Test accessing items by negative index."""
        assert keyed_list[-1] == sample_items[2]
        assert keyed_list[-2] == sample_items[1]
        assert keyed_list[-3] == sample_items[0]

    def test_getitem_out_of_range(self, keyed_list):
        """Test IndexError for out of range access."""
        with pytest.raises(IndexError):
            keyed_list[10]
        with pytest.raises(IndexError):
            keyed_list[-10]

    def test_setitem_by_index(self, keyed_list):
        """Test setting items by integer index."""
        new_item = Item("d", 4)
        keyed_list[0] = new_item
        assert keyed_list[0] == new_item
        assert keyed_list.get_by_key("d") == new_item
        # Old key should be removed
        assert keyed_list.get_by_key("a") is None

    def test_setitem_negative_index(self, keyed_list):
        """Test setting items by negative index."""
        new_item = Item("d", 4)
        keyed_list[-1] = new_item
        assert keyed_list[-1] == new_item
        assert keyed_list.get_by_key("d") == new_item
        assert keyed_list.get_by_key("c") is None

    def test_get_by_key(self, keyed_list, sample_items):
        """Test O(1) lookup by key."""
        assert keyed_list.get_by_key("a") == sample_items[0]
        assert keyed_list.get_by_key("b") == sample_items[1]
        assert keyed_list.get_by_key("c") == sample_items[2]
        assert keyed_list.get_by_key("nonexistent") is None

    def test_contains_by_item(self, keyed_list, sample_items):
        """Test membership testing by item."""
        assert sample_items[0] in keyed_list
        assert sample_items[1] in keyed_list
        assert Item("nonexistent", 999) not in keyed_list

    def test_contains_by_key(self, keyed_list):
        """Test membership testing by key."""
        assert keyed_list.has_key("a")
        assert keyed_list.has_key("b")
        assert keyed_list.has_key("c")
        assert not keyed_list.has_key("nonexistent")

    def test_delitem_by_index(self, keyed_list, sample_items):
        """Test deletion by index."""
        del keyed_list[1]  # Remove "b"
        assert len(keyed_list) == 2
        assert keyed_list[0] == sample_items[0]  # "a"
        assert keyed_list[1] == sample_items[2]  # "c"
        assert keyed_list.get_by_key("b") is None
        assert keyed_list.get_by_key("a") == sample_items[0]
        assert keyed_list.get_by_key("c") == sample_items[2]

    def test_delitem_by_key(self, keyed_list, sample_items):
        """Test deletion by key."""
        keyed_list.remove_by_key("b")
        assert len(keyed_list) == 2
        assert keyed_list[0] == sample_items[0]  # "a"
        assert keyed_list[1] == sample_items[2]  # "c"
        assert keyed_list.get_by_key("b") is None

    def test_append(self, keyed_list):
        """Test appending new items."""
        new_item = Item("d", 4)
        keyed_list.append(new_item)
        assert len(keyed_list) == 4
        assert keyed_list[3] == new_item
        assert keyed_list.get_by_key("d") == new_item

    def test_append_duplicate_key(self, keyed_list, sample_items):
        """Test appending item with duplicate key should replace."""
        new_item = Item("a", 100)  # Same key as first item
        keyed_list.append(new_item)
        assert len(keyed_list) == 3  # Should replace, not add
        assert keyed_list.get_by_key("a") == new_item
        # Should be at the end now
        assert keyed_list[2] == new_item

    def test_insert(self, keyed_list, sample_items):
        """Test inserting items at specific positions."""
        new_item = Item("d", 4)
        keyed_list.insert(1, new_item)
        assert len(keyed_list) == 4
        assert keyed_list[0] == sample_items[0]  # "a"
        assert keyed_list[1] == new_item  # "d"
        assert keyed_list[2] == sample_items[1]  # "b"
        assert keyed_list[3] == sample_items[2]  # "c"

    def test_reversed(self, keyed_list, sample_items):
        """Test reversed iteration."""
        reversed_items = list(reversed(keyed_list))
        assert reversed_items == [
            sample_items[2],
            sample_items[1],
            sample_items[0],
        ]

    def test_iteration(self, keyed_list, sample_items):
        """Test normal iteration."""
        items = list(keyed_list)
        assert items == sample_items

    def test_len(self, keyed_list):
        """Test length."""
        assert len(keyed_list) == 3

    def test_bool(self, keyed_list):
        """Test truthiness."""
        assert bool(keyed_list) is True
        empty_list = KeyedList([], lambda x: x.key)
        assert bool(empty_list) is False

    def test_serialization_as_list(self, keyed_list, sample_items):
        """Test that it behaves like a list for serialization."""
        # Should be able to convert to regular list
        as_list = list(keyed_list)
        assert as_list == sample_items

        # Should support list operations
        assert keyed_list[0:2] == sample_items[0:2]

    def test_key_function_change(self, sample_items):
        """Test that changing items affects key lookup."""
        kl = KeyedList(sample_items, lambda item: item.key)

        # Modify an item's key
        sample_items[0].key = "modified_a"

        # The keyed lookup should still work with original key since
        # the key mapping is created at init time
        assert kl.get_by_key("a") == sample_items[0]
        assert kl.get_by_key("modified_a") is None

    def test_duplicate_keys_at_init(self):
        """Test behavior with duplicate keys at initialization."""
        items = [Item("a", 1), Item("a", 2)]  # duplicate keys
        kl = KeyedList(items, lambda item: item.key)
        # Later item should win
        assert len(kl) == 1
        assert kl.get_by_key("a").value == 2
